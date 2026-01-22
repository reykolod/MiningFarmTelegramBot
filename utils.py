import asyncio
import os
import time
from aiogram.types import CallbackQuery, Message, InputMediaPhoto, FSInputFile
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter                                         
from database import db
from typing import Optional


_ui_message_by_chat_owner: dict[tuple[int, int, str], int] = {}
_ui_photo_message_by_chat_owner: dict[tuple[int, int, str], int] = {}
_ui_photo_file_by_chat_owner: dict[tuple[int, int, str], str] = {}
_ui_key_by_chat_owner_message: dict[tuple[int, int, int], str] = {}
_ui_photo_key_by_chat_owner_message: dict[tuple[int, int, int], str] = {}

_edit_lock_by_message: dict[tuple[int, int], asyncio.Lock] = {}
_edit_lock_by_chat: dict[int, asyncio.Lock] = {}
_last_edit_by_chat: dict[int, float] = {}
_last_send_by_chat: dict[int, float] = {}

_process_start_ts = time.monotonic()

_UI_MEDIA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "ui_media"))
_UI_MEDIA_ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _resolve_ui_media_file(photo_key: str) -> Optional[FSInputFile]:
    v = str(photo_key or "").strip()
    if not v:
        return None

    rel = v.lstrip("/\\")
    ext = os.path.splitext(rel)[1].lower()
    if ext and ext not in _UI_MEDIA_ALLOWED_EXTS:
        return None
    full = os.path.abspath(os.path.join(_UI_MEDIA_DIR, rel))
    base = _UI_MEDIA_DIR
    if not (full == base or full.startswith(base + os.sep)):
        return None
    if not os.path.isfile(full):
        return None
    try:
        return FSInputFile(full)
    except Exception:
        return None


def _norm_ui_key(ui_key: Optional[str]) -> str:
    v = str(ui_key or "").strip()
    return v if v else "default"


def get_ui_key_for_message(chat_id: int, owner_id: int, message_id: int) -> Optional[str]:
    return _ui_key_by_chat_owner_message.get((int(chat_id), int(owner_id), int(message_id)))


def get_ui_photo_key_for_message(chat_id: int, owner_id: int, message_id: int) -> Optional[str]:
    return _ui_photo_key_by_chat_owner_message.get((int(chat_id), int(owner_id), int(message_id)))


def set_ui_key_for_message(chat_id: int, owner_id: int, message_id: int, ui_key: Optional[str]) -> None:
    _ui_key_by_chat_owner_message[(int(chat_id), int(owner_id), int(message_id))] = _norm_ui_key(ui_key)


def set_ui_photo_key_for_message(chat_id: int, owner_id: int, message_id: int, photo_key: Optional[str]) -> None:
    key = (int(chat_id), int(owner_id), int(message_id))
    if photo_key is None:
        _ui_photo_key_by_chat_owner_message.pop(key, None)
    else:
        _ui_photo_key_by_chat_owner_message[key] = str(photo_key)


def _get_edit_lock(chat_id: int, message_id: int) -> asyncio.Lock:
    key = (int(chat_id), int(message_id))
    lock = _edit_lock_by_message.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _edit_lock_by_message[key] = lock
    return lock


def _get_chat_lock(chat_id: int) -> asyncio.Lock:
    key = int(chat_id)
    lock = _edit_lock_by_chat.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _edit_lock_by_chat[key] = lock
    return lock


async def safe_edit_message_text(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup=None,
    parse_mode: str = "HTML",
    disable_web_page_preview: Optional[bool] = None,
    min_interval_seconds: Optional[float] = None,
) -> bool:
    interval = (
        float(min_interval_seconds)
        if min_interval_seconds is not None
        else (1.0 if int(chat_id) < 0 else 0.25)
    )

    max_queue_wait_s = 3.0 if int(chat_id) < 0 else 1.5

    chat_key = int(chat_id)
    chat_lock = _get_chat_lock(chat_key)
    msg_lock = _get_edit_lock(chat_key, int(message_id))

    now_ts = time.monotonic()
    async with chat_lock:
        next_allowed_ts = _last_edit_by_chat.get(chat_key, 0.0)
        queue_wait_s = next_allowed_ts - now_ts
        if queue_wait_s > max_queue_wait_s:
            return False
        scheduled_ts = now_ts if now_ts > next_allowed_ts else next_allowed_ts
        _last_edit_by_chat[chat_key] = scheduled_ts + interval

    wait_s = scheduled_ts - now_ts
    if wait_s > 0:
        await asyncio.sleep(wait_s)

    async with msg_lock:
        for _attempt in range(2):
            try:
                await bot.edit_message_text(
                    chat_id=int(chat_id),
                    message_id=int(message_id),
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                )
                return True
            except TelegramBadRequest as e:
                if "message is not modified" in str(e).lower():
                    return True
                try:
                    await bot.edit_message_caption(
                        chat_id=int(chat_id),
                        message_id=int(message_id),
                        caption=text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode,
                    )
                    return True
                except Exception:
                    return False
            except TelegramRetryAfter as e:
                retry_after_s = float(getattr(e, "retry_after", 1) or 1)
                async with chat_lock:
                    n = time.monotonic()
                    _last_edit_by_chat[chat_key] = max(_last_edit_by_chat.get(chat_key, 0.0), n + retry_after_s)
                await asyncio.sleep(retry_after_s)

    return False


async def safe_edit_message_photo(
    bot: Bot,
    chat_id: int,
    message_id: int,
    photo: str,
    caption: str,
    reply_markup=None,
    parse_mode: str = "HTML",
    min_interval_seconds: Optional[float] = None,
) -> bool:
    interval = (
        float(min_interval_seconds)
        if min_interval_seconds is not None
        else (1.0 if int(chat_id) < 0 else 0.25)
    )

    max_queue_wait_s = 3.0 if int(chat_id) < 0 else 1.5

    chat_key = int(chat_id)
    chat_lock = _get_chat_lock(chat_key)
    msg_lock = _get_edit_lock(chat_key, int(message_id))

    now_ts = time.monotonic()
    async with chat_lock:
        next_allowed_ts = _last_edit_by_chat.get(chat_key, 0.0)
        queue_wait_s = next_allowed_ts - now_ts
        if queue_wait_s > max_queue_wait_s:
            return False
        scheduled_ts = now_ts if now_ts > next_allowed_ts else next_allowed_ts
        _last_edit_by_chat[chat_key] = scheduled_ts + interval

    wait_s = scheduled_ts - now_ts
    if wait_s > 0:
        await asyncio.sleep(wait_s)

    photo_file = _resolve_ui_media_file(photo)
    if photo_file is None:
        return False

    async with msg_lock:
        for _attempt in range(2):
            try:
                await bot.edit_message_media(
                    chat_id=int(chat_id),
                    message_id=int(message_id),
                    media=InputMediaPhoto(
                        media=photo_file,
                        caption=str(caption),
                        parse_mode=parse_mode,
                    ),
                    reply_markup=reply_markup,
                )
                return True
            except TelegramBadRequest as e:
                if "message is not modified" in str(e).lower():
                    return True
                return False
            except TelegramRetryAfter as e:
                retry_after_s = float(getattr(e, "retry_after", 1) or 1)
                async with chat_lock:
                    n = time.monotonic()
                    _last_edit_by_chat[chat_key] = max(_last_edit_by_chat.get(chat_key, 0.0), n + retry_after_s)
                await asyncio.sleep(retry_after_s)

    return False


def get_process_uptime_seconds() -> float:
    return time.monotonic() - _process_start_ts


def get_edit_debug_stats() -> dict:
    now_ts = time.monotonic()
    if _last_edit_by_chat:
        next_allowed = min(_last_edit_by_chat.values())
        worst_allowed = max(_last_edit_by_chat.values())
        min_wait = max(0.0, next_allowed - now_ts)
        max_wait = max(0.0, worst_allowed - now_ts)
    else:
        min_wait = 0.0
        max_wait = 0.0

    return {
        "ui_messages": len(_ui_message_by_chat_owner),
        "message_locks": len(_edit_lock_by_message),
        "chat_locks": len(_edit_lock_by_chat),
        "rate_chats": len(_last_edit_by_chat),
        "send_rate_chats": len(_last_send_by_chat),
        "min_wait_s": float(min_wait),
        "max_wait_s": float(max_wait),
    }


async def safe_send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup=None,
    parse_mode: str = "HTML",
    disable_web_page_preview: Optional[bool] = None,
    reply_to_message_id: Optional[int] = None,
    min_interval_seconds: Optional[float] = None,
):
    interval = (
        float(min_interval_seconds)
        if min_interval_seconds is not None
        else (1.0 if int(chat_id) < 0 else 0.25)
    )

    chat_key = int(chat_id)
    chat_lock = _get_chat_lock(chat_key)

    now_ts = time.monotonic()
    async with chat_lock:
        next_allowed_ts = _last_send_by_chat.get(chat_key, 0.0)
        scheduled_ts = now_ts if now_ts > next_allowed_ts else next_allowed_ts
        _last_send_by_chat[chat_key] = scheduled_ts + interval

    wait_s = scheduled_ts - now_ts
    if wait_s > 0:
        await asyncio.sleep(wait_s)

    for _attempt in range(2):
        try:
            return await bot.send_message(
                chat_id=int(chat_id),
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
                reply_to_message_id=int(reply_to_message_id) if reply_to_message_id is not None else None,
            )
        except TelegramRetryAfter as e:
            retry_after_s = float(getattr(e, "retry_after", 1) or 1)
            async with chat_lock:
                n = time.monotonic()
                _last_send_by_chat[chat_key] = max(_last_send_by_chat.get(chat_key, 0.0), n + retry_after_s)
            await asyncio.sleep(retry_after_s)
        except TelegramBadRequest:
            return None
        except Exception:
            return None

    return None


async def render_ui_photo_from_callback(
    callback: CallbackQuery,
    owner_id: int,
    photo: str,
    caption: str,
    *,
    parse_mode: str = "HTML",
    ui_key: Optional[str] = None,
) -> Optional[int]:
    msg = callback.message
    if msg is None or msg.chat is None:
        return None

    chat_id = int(msg.chat.id)
    ui_key_value = _norm_ui_key(ui_key or get_ui_key_for_message(chat_id, int(owner_id), int(msg.message_id)))
    prev_photo_id = get_ui_photo_message_id(chat_id, int(owner_id), ui_key_value)
    prev_file_id = get_ui_photo_file_id(chat_id, int(owner_id), ui_key_value)
    if prev_photo_id is not None and prev_file_id == str(photo):
        return int(prev_photo_id)

    sent = await safe_send_photo(
        bot=callback.bot,
        chat_id=chat_id,
        photo=str(photo),
        caption=str(caption),
        reply_markup=None,
        parse_mode=parse_mode,
        reply_to_message_id=int(msg.message_id),
    )

    if sent is None:
        return None

    new_id = int(sent.message_id)
    set_ui_photo_message_id(chat_id, int(owner_id), ui_key_value, new_id)
    set_ui_photo_file_id(chat_id, int(owner_id), ui_key_value, str(photo))

    if prev_photo_id is not None and int(prev_photo_id) != new_id:
        try:
            await _safe_delete_message(callback.bot, chat_id, int(prev_photo_id))
        except Exception:
            pass

    return new_id


async def clear_ui_photo_from_callback(
    callback: CallbackQuery,
    owner_id: int,
    *,
    ui_key: Optional[str] = None,
) -> None:
    msg = callback.message
    if msg is None or msg.chat is None:
        return

    chat_id = int(msg.chat.id)
    ui_key_value = _norm_ui_key(ui_key or get_ui_key_for_message(chat_id, int(owner_id), int(msg.message_id)))
    prev_photo_id = get_ui_photo_message_id(chat_id, int(owner_id), ui_key_value)
    if prev_photo_id is None:
        return

    set_ui_photo_message_id(chat_id, int(owner_id), ui_key_value, None)
    set_ui_photo_file_id(chat_id, int(owner_id), ui_key_value, None)
    try:
        await _safe_delete_message(callback.bot, chat_id, int(prev_photo_id))
    except Exception:
        pass


async def render_ui_photo_from_message(
    message: Message,
    owner_id: int,
    photo: str,
    caption: str,
    *,
    parse_mode: str = "HTML",
    reply_to_message_id: Optional[int] = None,
    ui_key: Optional[str] = None,
) -> Optional[int]:
    if message.chat is None:
        return None

    chat_id = int(message.chat.id)
    ui_key_value = _norm_ui_key(ui_key)
    prev_photo_id = get_ui_photo_message_id(chat_id, int(owner_id), ui_key_value)
    prev_file_id = get_ui_photo_file_id(chat_id, int(owner_id), ui_key_value)
    if prev_photo_id is not None and prev_file_id == str(photo):
        return int(prev_photo_id)

    sent = await safe_send_photo(
        bot=message.bot,
        chat_id=chat_id,
        photo=str(photo),
        caption=str(caption),
        reply_markup=None,
        parse_mode=parse_mode,
        reply_to_message_id=(
            int(reply_to_message_id)
            if reply_to_message_id is not None
            else int(message.message_id)
        ),
    )

    if sent is None:
        return None

    new_id = int(sent.message_id)
    set_ui_photo_message_id(chat_id, int(owner_id), ui_key_value, new_id)
    set_ui_photo_file_id(chat_id, int(owner_id), ui_key_value, str(photo))

    if prev_photo_id is not None and int(prev_photo_id) != new_id:
        try:
            await _safe_delete_message(message.bot, chat_id, int(prev_photo_id))
        except Exception:
            pass

    return new_id


async def clear_ui_photo_from_message(
    message: Message,
    owner_id: int,
    *,
    ui_key: Optional[str] = None,
) -> None:
    if message.chat is None:
        return

    chat_id = int(message.chat.id)
    ui_key_value = _norm_ui_key(ui_key)
    prev_photo_id = get_ui_photo_message_id(chat_id, int(owner_id), ui_key_value)
    if prev_photo_id is None:
        return

    set_ui_photo_message_id(chat_id, int(owner_id), ui_key_value, None)
    set_ui_photo_file_id(chat_id, int(owner_id), ui_key_value, None)
    try:
        await _safe_delete_message(message.bot, chat_id, int(prev_photo_id))
    except Exception:
        pass


async def safe_send_photo(
    bot: Bot,
    chat_id: int,
    photo: str,
    caption: str,
    reply_markup=None,
    parse_mode: str = "HTML",
    reply_to_message_id: Optional[int] = None,
    min_interval_seconds: Optional[float] = None,
):
    interval = (
        float(min_interval_seconds)
        if min_interval_seconds is not None
        else (1.0 if int(chat_id) < 0 else 0.25)
    )

    chat_key = int(chat_id)
    chat_lock = _get_chat_lock(chat_key)

    now_ts = time.monotonic()
    async with chat_lock:
        next_allowed_ts = _last_send_by_chat.get(chat_key, 0.0)
        scheduled_ts = now_ts if now_ts > next_allowed_ts else next_allowed_ts
        _last_send_by_chat[chat_key] = scheduled_ts + interval

    wait_s = scheduled_ts - now_ts
    if wait_s > 0:
        await asyncio.sleep(wait_s)

    photo_file = _resolve_ui_media_file(photo)
    if photo_file is None:
        return None

    for _attempt in range(2):
        try:
            return await bot.send_photo(
                chat_id=int(chat_id),
                photo=photo_file,
                caption=str(caption),
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                reply_to_message_id=int(reply_to_message_id) if reply_to_message_id is not None else None,
            )
        except TelegramRetryAfter as e:
            retry_after_s = float(getattr(e, "retry_after", 1) or 1)
            async with chat_lock:
                n = time.monotonic()
                _last_send_by_chat[chat_key] = max(_last_send_by_chat.get(chat_key, 0.0), n + retry_after_s)
            await asyncio.sleep(retry_after_s)
        except TelegramBadRequest:
            return None
        except Exception:
            return None

    return None


def get_ui_message_id(chat_id: int, owner_id: int, ui_key: Optional[str] = None) -> Optional[int]:
    return _ui_message_by_chat_owner.get((int(chat_id), int(owner_id), _norm_ui_key(ui_key)))


def set_ui_message_id(chat_id: int, owner_id: int, message_id: Optional[int], ui_key: Optional[str] = None) -> None:
    key = (int(chat_id), int(owner_id), _norm_ui_key(ui_key))
    prev_id = _ui_message_by_chat_owner.get(key)
    if message_id is None:
        _ui_message_by_chat_owner.pop(key, None)
        if prev_id is not None:
            _ui_key_by_chat_owner_message.pop((int(chat_id), int(owner_id), int(prev_id)), None)
            _ui_photo_key_by_chat_owner_message.pop((int(chat_id), int(owner_id), int(prev_id)), None)
        return

    new_id = int(message_id)
    _ui_message_by_chat_owner[key] = new_id
    _ui_key_by_chat_owner_message[(int(chat_id), int(owner_id), new_id)] = key[2]
    if prev_id is not None and int(prev_id) != new_id:
        _ui_key_by_chat_owner_message.pop((int(chat_id), int(owner_id), int(prev_id)), None)
        _ui_photo_key_by_chat_owner_message.pop((int(chat_id), int(owner_id), int(prev_id)), None)


def _get_all_ui_message_entries(chat_id: int, owner_id: int) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    cid = int(chat_id)
    oid = int(owner_id)
    for (k_chat_id, k_owner_id, k_ui_key), msg_id in list(_ui_message_by_chat_owner.items()):
        if int(k_chat_id) == cid and int(k_owner_id) == oid and msg_id is not None:
            entries.append((str(k_ui_key), int(msg_id)))
    return entries


def get_ui_photo_message_id(chat_id: int, owner_id: int, ui_key: Optional[str] = None) -> Optional[int]:
    return _ui_photo_message_by_chat_owner.get((int(chat_id), int(owner_id), _norm_ui_key(ui_key)))


def set_ui_photo_message_id(chat_id: int, owner_id: int, ui_key: Optional[str], message_id: Optional[int]) -> None:
    key = (int(chat_id), int(owner_id), _norm_ui_key(ui_key))
    if message_id is None:
        _ui_photo_message_by_chat_owner.pop(key, None)
    else:
        _ui_photo_message_by_chat_owner[key] = int(message_id)


def get_ui_photo_file_id(chat_id: int, owner_id: int, ui_key: Optional[str] = None) -> Optional[str]:
    value = _ui_photo_file_by_chat_owner.get((int(chat_id), int(owner_id), _norm_ui_key(ui_key)))
    return str(value) if value else None


def set_ui_photo_file_id(chat_id: int, owner_id: int, ui_key: Optional[str], file_id: Optional[str]) -> None:
    key = (int(chat_id), int(owner_id), _norm_ui_key(ui_key))
    if file_id is None or not str(file_id).strip():
        _ui_photo_file_by_chat_owner.pop(key, None)
    else:
        _ui_photo_file_by_chat_owner[key] = str(file_id)


async def _safe_delete_message(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=int(chat_id), message_id=int(message_id))
    except Exception:
        pass


async def _safe_deactivate_message(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.edit_message_reply_markup(
            chat_id=int(chat_id),
            message_id=int(message_id),
            reply_markup=None,
        )
    except Exception:
        pass


async def register_ui_message(bot: Bot, chat_id: int, owner_id: int, message_id: int, *, ui_key: Optional[str] = None) -> None:
    key_value = _norm_ui_key(ui_key)
    set_ui_message_id(int(chat_id), int(owner_id), int(message_id), key_value)


async def render_ui_from_message(
    message: Message,
    owner_id: int,
    text: str,
    reply_markup,
    parse_mode: str = "HTML",
    disable_web_page_preview: Optional[bool] = None,
    prefer_reply_in_groups: bool = True,
    ui_key: Optional[str] = None,
    photo: Optional[str] = None,
) -> Optional[int]:
    if message.chat is None:
        return None

    chat_id = int(message.chat.id)
    ui_key_value = _norm_ui_key(ui_key)

    desired_photo: Optional[str]
    if photo is None:
        desired_photo = None
    else:
        desired_photo = str(photo).strip()

    raw_text = (getattr(message, "text", None) or "").lstrip()
    entities = getattr(message, "entities", None) or []
    is_command_message = False
    if raw_text.startswith("/"):
        is_command_message = True
        try:
            for e in entities:
                if getattr(e, "type", None) == "bot_command" and int(getattr(e, "offset", 0) or 0) == 0:
                    is_command_message = True
                    break
        except Exception:
            is_command_message = True

    old_ui_entries: list[tuple[str, int]] = []
    if is_command_message:
        old_ui_entries = _get_all_ui_message_entries(chat_id, int(owner_id))

    bot = getattr(message, "bot", None)
    if bot is not None and not is_command_message:
        ui_message_id = get_ui_message_id(chat_id, owner_id, ui_key_value)
        prev_photo_file_id = get_ui_photo_file_id(chat_id, int(owner_id), ui_key_value)
        if ui_message_id is not None:
                                                                         
            if desired_photo is None:
                ok = await safe_edit_message_text(
                    bot=bot,
                    chat_id=chat_id,
                    message_id=int(ui_message_id),
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                )
                if ok:
                    _ui_key_by_chat_owner_message[(int(chat_id), int(owner_id), int(ui_message_id))] = ui_key_value
                    return int(ui_message_id)

                                                                                                  
            elif desired_photo == "":
                if prev_photo_file_id is None:
                    ok = await safe_edit_message_text(
                        bot=bot,
                        chat_id=chat_id,
                        message_id=int(ui_message_id),
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode,
                        disable_web_page_preview=disable_web_page_preview,
                    )
                    if ok:
                        _ui_key_by_chat_owner_message[(int(chat_id), int(owner_id), int(ui_message_id))] = ui_key_value
                        return int(ui_message_id)
                else:
                    ui_message_id = None

                                                                                               
            else:
                if prev_photo_file_id is None:
                    ui_message_id = None
                else:
                    if prev_photo_file_id == desired_photo:
                        ok = await safe_edit_message_text(
                            bot=bot,
                            chat_id=chat_id,
                            message_id=int(ui_message_id),
                            text=text,
                            reply_markup=reply_markup,
                            parse_mode=parse_mode,
                            disable_web_page_preview=disable_web_page_preview,
                        )
                    else:
                        ok = await safe_edit_message_photo(
                            bot=bot,
                            chat_id=chat_id,
                            message_id=int(ui_message_id),
                            photo=desired_photo,
                            caption=str(text),
                            reply_markup=reply_markup,
                            parse_mode=parse_mode,
                        )
                    if ok:
                        _ui_key_by_chat_owner_message[(int(chat_id), int(owner_id), int(ui_message_id))] = ui_key_value
                        set_ui_photo_file_id(chat_id, int(owner_id), ui_key_value, desired_photo)
                        set_ui_photo_key_for_message(chat_id, int(owner_id), int(ui_message_id), desired_photo)
                        return int(ui_message_id)

    if message.chat.type != "private" and prefer_reply_in_groups:
        try:
            prev_ui_message_id = get_ui_message_id(chat_id, owner_id, ui_key_value)
            if desired_photo:
                sent = await safe_send_photo(
                    bot=message.bot,
                    chat_id=chat_id,
                    photo=str(desired_photo),
                    caption=str(text),
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    reply_to_message_id=int(message.message_id),
                )
                if sent is None:
                    sent = await safe_send_message(
                        bot=message.bot,
                        chat_id=chat_id,
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode,
                        disable_web_page_preview=disable_web_page_preview,
                        reply_to_message_id=int(message.message_id),
                    )
            else:
                sent = await safe_send_message(
                    bot=message.bot,
                    chat_id=chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                    reply_to_message_id=int(message.message_id),
                )
            if sent is not None:
                sent_has_photo = bool(getattr(sent, "photo", None))
                new_id = int(sent.message_id)
                set_ui_message_id(chat_id, owner_id, new_id, ui_key_value)
                if sent_has_photo and desired_photo:
                    set_ui_photo_file_id(chat_id, int(owner_id), ui_key_value, str(desired_photo))
                    set_ui_photo_key_for_message(chat_id, int(owner_id), int(new_id), str(desired_photo))
                else:
                    set_ui_photo_file_id(chat_id, int(owner_id), ui_key_value, None)
                    set_ui_photo_key_for_message(chat_id, int(owner_id), int(new_id), None)

                if is_command_message and old_ui_entries:
                    for key_value, msg_id in old_ui_entries:
                        if int(msg_id) == new_id:
                            continue
                        try:
                            await _safe_delete_message(message.bot, chat_id, int(msg_id))
                        except Exception:
                            try:
                                await _safe_deactivate_message(message.bot, chat_id, int(msg_id))
                            except Exception:
                                pass
                        if key_value != ui_key_value:
                            set_ui_message_id(chat_id, int(owner_id), None, key_value)
                            set_ui_photo_file_id(chat_id, int(owner_id), key_value, None)

                if prev_ui_message_id is not None and int(prev_ui_message_id) != new_id:
                    try:
                        await _safe_delete_message(message.bot, chat_id, int(prev_ui_message_id))
                    except Exception:
                        try:
                            await _safe_deactivate_message(message.bot, chat_id, int(prev_ui_message_id))
                        except Exception:
                            pass

                return new_id
        except Exception:
            pass

    try:
        prev_ui_message_id = get_ui_message_id(chat_id, owner_id, ui_key_value)
        if desired_photo:
            sent = await safe_send_photo(
                bot=message.bot,
                chat_id=chat_id,
                photo=str(desired_photo),
                caption=str(text),
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            if sent is None:
                sent = await safe_send_message(
                    bot=message.bot,
                    chat_id=chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                )
        else:
            sent = await safe_send_message(
                bot=message.bot,
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
        if sent is None:
            return None

        sent_has_photo = bool(getattr(sent, "photo", None))
        new_id = int(sent.message_id)
        set_ui_message_id(chat_id, owner_id, new_id, ui_key_value)
        if sent_has_photo and desired_photo:
            set_ui_photo_file_id(chat_id, int(owner_id), ui_key_value, str(desired_photo))
            set_ui_photo_key_for_message(chat_id, int(owner_id), int(new_id), str(desired_photo))
        else:
            set_ui_photo_file_id(chat_id, int(owner_id), ui_key_value, None)
            set_ui_photo_key_for_message(chat_id, int(owner_id), int(new_id), None)

        if is_command_message and old_ui_entries:
            for key_value, msg_id in old_ui_entries:
                if int(msg_id) == new_id:
                    continue
                try:
                    await _safe_delete_message(message.bot, chat_id, int(msg_id))
                except Exception:
                    try:
                        await _safe_deactivate_message(message.bot, chat_id, int(msg_id))
                    except Exception:
                        pass
                if key_value != ui_key_value:
                    set_ui_message_id(chat_id, int(owner_id), None, key_value)
                    set_ui_photo_file_id(chat_id, int(owner_id), key_value, None)

        if prev_ui_message_id is not None and int(prev_ui_message_id) != new_id:
            try:
                await _safe_delete_message(message.bot, chat_id, int(prev_ui_message_id))
            except Exception:
                try:
                    await _safe_deactivate_message(message.bot, chat_id, int(prev_ui_message_id))
                except Exception:
                    pass

        return new_id
    except Exception:
        return None


async def render_ui_from_callback(
    callback: CallbackQuery,
    owner_id: int,
    text: str,
    reply_markup,
    parse_mode: str = "HTML",
    disable_web_page_preview: Optional[bool] = None,
    ui_key: Optional[str] = None,
    photo: Optional[str] = None,
) -> Optional[int]:
    msg = callback.message
    if msg is None or msg.chat is None:
        return None

    chat_id = int(msg.chat.id)
    message_id = int(msg.message_id)
    ui_key_value = _norm_ui_key(ui_key or get_ui_key_for_message(chat_id, int(owner_id), int(message_id)))

    desired_photo: Optional[str]
    if photo is None:
        desired_photo = None
    else:
        desired_photo = str(photo).strip()

    message_has_photo = bool(getattr(msg, "photo", None))
    current_photo_key = get_ui_photo_key_for_message(chat_id, int(owner_id), int(message_id))
    if message_has_photo and current_photo_key is None:
        tracked = get_ui_photo_file_id(chat_id, int(owner_id), ui_key_value)
        if tracked:
            current_photo_key = str(tracked)
            set_ui_photo_key_for_message(chat_id, int(owner_id), int(message_id), current_photo_key)

                                                     
    set_ui_message_id(chat_id, int(owner_id), int(message_id), ui_key_value)

                                                                   
    if desired_photo is None:
        ok = await safe_edit_message_text(
            bot=callback.bot,
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )
        if ok:
            return message_id
        return None

                                                                                          
    if desired_photo == "":
        if not message_has_photo:
            ok = await safe_edit_message_text(
                bot=callback.bot,
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
            if ok:
                set_ui_photo_file_id(chat_id, int(owner_id), ui_key_value, None)
                set_ui_photo_key_for_message(chat_id, int(owner_id), int(message_id), None)
                return message_id
                           

                                            
    if desired_photo != "" and message_has_photo:
        if current_photo_key is not None and current_photo_key == desired_photo:
            ok = await safe_edit_message_text(
                bot=callback.bot,
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
        else:
            ok = await safe_edit_message_photo(
                bot=callback.bot,
                chat_id=chat_id,
                message_id=message_id,
                photo=desired_photo,
                caption=str(text),
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )

        if ok:
            set_ui_photo_file_id(chat_id, int(owner_id), ui_key_value, desired_photo)
            set_ui_photo_key_for_message(chat_id, int(owner_id), int(message_id), desired_photo)
            return message_id

                                                                                                      
    sent = None
    if desired_photo:
        sent = await safe_send_photo(
            bot=callback.bot,
            chat_id=chat_id,
            photo=str(desired_photo),
            caption=str(text),
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        if sent is None:
            sent = await safe_send_message(
                bot=callback.bot,
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
    else:
        sent = await safe_send_message(
            bot=callback.bot,
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )

    if sent is None:
        return None

    new_id = int(sent.message_id)
    set_ui_message_id(chat_id, int(owner_id), new_id, ui_key_value)
    sent_has_photo = bool(getattr(sent, "photo", None))
    if sent_has_photo and desired_photo:
        set_ui_photo_file_id(chat_id, int(owner_id), ui_key_value, desired_photo)
        set_ui_photo_key_for_message(chat_id, int(owner_id), int(new_id), desired_photo)
    else:
        set_ui_photo_file_id(chat_id, int(owner_id), ui_key_value, None)
        set_ui_photo_key_for_message(chat_id, int(owner_id), int(new_id), None)

    try:
        await _safe_delete_message(callback.bot, chat_id, int(message_id))
    except Exception:
        try:
            await _safe_deactivate_message(callback.bot, chat_id, int(message_id))
        except Exception:
            pass

    set_ui_photo_key_for_message(chat_id, int(owner_id), int(message_id), None)

    return new_id


def check_message_owner(callback: CallbackQuery, required_user_id: int = None) -> tuple[bool, int]:
    user_id = callback.from_user.id
    
                                                                
    if required_user_id is not None:
        if user_id != required_user_id:
            return False, user_id
        return True, user_id
    
                                                                  
                                                                           
    if callback.message.chat.type != "private":
                                                         
        return False, user_id
    
                                         
    return True, user_id


async def handle_unauthorized_access(callback: CallbackQuery):
    try:
        data = callback.data or ""
        parts = data.split("_")
        if parts:
            try:
                owner_id = int(parts[-1])
            except ValueError:
                owner_id = None
        else:
            owner_id = None

        if owner_id is not None and int(owner_id) == int(callback.from_user.id):
            await callback.answer("ℹ️ Кнопка устарела. Откройте меню заново: /mining", show_alert=True)
            return
    except Exception:
        pass

    await callback.answer("❌ Это не ваша ферма! Используйте /mining для создания своей.", show_alert=True)


def check_user_banned(user_id: int) -> tuple[bool, Optional[str]]:
    from database import db
    is_banned = db.is_user_banned(user_id)
    if is_banned:
        reason = db.get_ban_reason(user_id) or "Нарушение правил"
        return True, reason
    return False, None


async def send_notification(
    bot: Bot,
    target_user_id: int,
    notification_text: str,
    fallback_chat_id: int = None,
    parse_mode: str = "HTML"
) -> bool:
    try:
                                               
        await bot.send_message(
            chat_id=target_user_id,
            text=notification_text,
            parse_mode=parse_mode
        )
        return True
    except Exception:
                                                                                         
        if fallback_chat_id:
            try:
                await bot.send_message(
                    chat_id=fallback_chat_id,
                    text=notification_text,
                    parse_mode=parse_mode
                )
                return True
            except Exception:
                pass
        return False


def save_chat_from_message(message: Message):
    if not message or not message.chat:
        return
    chat_id = message.chat.id
    chat_type = message.chat.type
    title = message.chat.title or ""
    username = getattr(message.chat, "username", None) or ""
    db.add_chat_if_not_exists(chat_id, chat_type, title, username=username)


def save_chat_from_callback(callback: CallbackQuery):
    if not callback or not callback.message or not callback.message.chat:
        return
    chat_id = callback.message.chat.id
    chat_type = callback.message.chat.type
    title = callback.message.chat.title or ""
    username = getattr(callback.message.chat, "username", None) or ""
    db.add_chat_if_not_exists(chat_id, chat_type, title, username=username)
