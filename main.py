import asyncio
import logging
import os
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict
from aiogram import Bot, Dispatcher, Router, F                                         
from aiogram.client.default import DefaultBotProperties                                         
from aiogram.enums import ParseMode                                         
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile                                         
from aiogram.dispatcher.middlewares.base import BaseMiddleware                                         
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError                                         
from config import BOT_TOKEN, ADMIN_ID, DB_BACKUP_CHAT_ID
from database import db
from utils import safe_send_message, safe_edit_message_text

from exchange_rate import trigger_bitcoin_rate_refresh

try:
    from zoneinfo import ZoneInfo
except Exception:                    
    ZoneInfo = None                            

                      
from handlers import (
    start,
    shop,
    mining,
    wallet,
    inventory,
    equipment,
    admin,
    category_images,
    leaderboard,
    report,
    transfer,
    profile,
    clans,
    synapse,
    wiki,
    info,
)

                       
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

                                                                                         
logging.getLogger("aiogram.event").setLevel(logging.WARNING)


_last_group_only_prompt_by_user: dict[int, float] = {}
_cached_bot_username: str | None = None
_cached_bot_username_ts: float = 0.0


async def _get_bot_username(bot: Bot) -> str | None:
    global _cached_bot_username, _cached_bot_username_ts
    now_ts = time.monotonic()
    if _cached_bot_username is not None and now_ts - float(_cached_bot_username_ts) < 3600.0:
        return _cached_bot_username
    try:
        me = await bot.get_me()
        username = getattr(me, "username", None)
        if username:
            _cached_bot_username = str(username)
            _cached_bot_username_ts = now_ts
            return _cached_bot_username
    except Exception:
        pass
    return _cached_bot_username


def _invite_to_chat_keyboard(bot_username: str | None) -> InlineKeyboardMarkup | None:
    if not bot_username:
        return None
    url = f"https://t.me/{bot_username}?startgroup=true"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Пригласить в чат", url=url)]]
    )


class GroupOnlyMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any],
    ) -> Any:
        chat = getattr(event, "chat", None)
        if chat is None and isinstance(event, CallbackQuery):
            msg = getattr(event, "message", None)
            chat = getattr(msg, "chat", None) if msg is not None else None

        chat_type = getattr(chat, "type", None) if chat is not None else None
        if chat_type != "private":
            return await handler(event, data)

        from_user = data.get("event_from_user")
        if from_user is None:
            from_user = getattr(event, "from_user", None)
        user_id = getattr(from_user, "id", None) if from_user is not None else None

        if ADMIN_ID and user_id == ADMIN_ID:
            return await handler(event, data)

        bot = data.get("bot")
        if bot is None:
            bot = getattr(event, "bot", None)
        if bot is None:
            return None

        now_ts = time.monotonic()
        if user_id is not None:
            last_ts = _last_group_only_prompt_by_user.get(int(user_id), 0.0)
            if now_ts - float(last_ts) < 10.0:
                try:
                    if isinstance(event, CallbackQuery):
                        await event.answer()
                except Exception:
                    pass
                return None
            _last_group_only_prompt_by_user[int(user_id)] = now_ts

        try:
            if isinstance(event, CallbackQuery):
                await event.answer()
        except Exception:
            pass

        text = (
            "🚫 Этот бот работает только в группах.\n\n"
            "Добавьте бота в свой чат и пользуйтесь командами там."
        )

        try:
            chat_id = getattr(chat, "id", None) if chat is not None else None
            if chat_id is None:
                return None
            username = await _get_bot_username(bot)
            await safe_send_message(
                bot=bot,
                chat_id=int(chat_id),
                text=text,
                reply_markup=_invite_to_chat_keyboard(username),
            )
        except Exception:
            pass
        return None


class BanIgnoreMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any],
    ) -> Any:
        from_user = data.get("event_from_user")
        if from_user is None:
            from_user = getattr(event, "from_user", None)

        if from_user is None:
            for _attr in (
                "message",
                "edited_message",
                "callback_query",
                "inline_query",
                "chosen_inline_result",
                "shipping_query",
                "pre_checkout_query",
                "my_chat_member",
                "chat_member",
            ):
                _obj = getattr(event, _attr, None)
                _candidate = getattr(_obj, "from_user", None) if _obj is not None else None
                if _candidate is not None:
                    from_user = _candidate
                    break

        if from_user is None:
            return await handler(event, data)

        user_id = getattr(from_user, "id", None)
        if user_id is None:
            return await handler(event, data)

        if ADMIN_ID and user_id == ADMIN_ID:
            return await handler(event, data)

        try:
            if db.is_user_banned(int(user_id)):
                return None
        except Exception:
            return await handler(event, data)

        return await handler(event, data)


NEWS_CHANNEL = "@rSynapse"
NEWS_CHANNEL_URL = "https://t.me/rSynapse"
CHECK_SUB_CALLBACK = "check_news_subscription"
SUB_CHECK_CACHE_TTL_S = 120.0
_last_sub_check_by_user: dict[int, tuple[bool, float]] = {}
_last_sub_prompt_by_user: dict[int, float] = {}


def _subscription_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подписаться", url=NEWS_CHANNEL_URL)],
            [
                InlineKeyboardButton(
                    text="Проверить подписку",
                    callback_data=f"{CHECK_SUB_CALLBACK}_{int(owner_id)}",
                )
            ],
        ]
    )


async def _is_user_subscribed(bot: Bot, user_id: int, *, force_refresh: bool = False) -> bool:
    now_ts = time.monotonic()
    cached = _last_sub_check_by_user.get(user_id)
    if not force_refresh:
        if cached is not None:
            cached_ok, cached_ts = cached
            if now_ts - cached_ts < SUB_CHECK_CACHE_TTL_S:
                return cached_ok

    try:
        member = await bot.get_chat_member(NEWS_CHANNEL, user_id)
        status = getattr(member, "status", None)
        ok = status in {"member", "administrator", "creator"}
    except (TelegramBadRequest, TelegramForbiddenError):
        ok = False
    except Exception:
        if cached is not None:
            ok, _cached_ts = cached
        else:
            ok = False

    _last_sub_check_by_user[user_id] = (ok, now_ts)
    return ok


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any],
    ) -> Any:
        from_user = data.get("event_from_user")
        if from_user is None:
            from_user = getattr(event, "from_user", None)

        if from_user is None:
            for _attr in (
                "message",
                "edited_message",
                "callback_query",
                "inline_query",
                "chosen_inline_result",
                "shipping_query",
                "pre_checkout_query",
            ):
                _obj = getattr(event, _attr, None)
                _candidate = getattr(_obj, "from_user", None) if _obj is not None else None
                if _candidate is not None:
                    from_user = _candidate
                    break

        if from_user is None:
            return await handler(event, data)

        user_id = getattr(from_user, "id", None)
        if user_id is None:
            return await handler(event, data)

        if ADMIN_ID and int(user_id) == ADMIN_ID:
            return await handler(event, data)

                                                              
                                                                   
        if isinstance(event, Message):
            text = (event.text or "").lstrip()
            is_command = False
            if text.startswith("/"):
                is_command = True
            else:
                entities = getattr(event, "entities", None) or []
                for ent in entities:
                    try:
                        if getattr(ent, "type", None) == "bot_command" and int(getattr(ent, "offset", 0)) == 0:
                            is_command = True
                            break
                    except Exception:
                        continue

            if not is_command:
                return await handler(event, data)
        else:
            return await handler(event, data)

        bot = data.get("bot")
        if bot is None:
            bot = getattr(event, "bot", None)

        if bot is None:
            return await handler(event, data)

        is_ok = await _is_user_subscribed(bot, int(user_id))
        if is_ok:
            return await handler(event, data)

        chat_id = None
        reply_to_message_id = None
        if isinstance(event, CallbackQuery) and event.message is not None:
            chat_id = event.message.chat.id
        elif isinstance(event, Message):
            chat_id = event.chat.id
            if event.chat.type in ("group", "supergroup"):
                reply_to_message_id = event.message_id
        else:
            chat = getattr(event, "chat", None)
            if chat is not None:
                chat_id = getattr(chat, "id", None)

        now_ts = time.monotonic()
        last_prompt_ts = _last_sub_prompt_by_user.get(int(user_id), 0.0)
        min_prompt_interval_s = 2.0
        if isinstance(event, Message):
            try:
                if getattr(event.chat, "type", "private") in ("group", "supergroup"):
                    min_prompt_interval_s = 10.0
            except Exception:
                pass

        if now_ts - last_prompt_ts < min_prompt_interval_s:
            try:
                if isinstance(event, CallbackQuery):
                    await event.answer()
            except Exception:
                pass
            return None

        _last_sub_prompt_by_user[int(user_id)] = now_ts

        text = (
            "❗️Чтобы пользоваться ботом, нужно подписаться на канал с новостями.\n\n"
            "После подписки нажмите «Проверить подписку»."
        )

        try:
            if isinstance(event, CallbackQuery):
                await event.answer()
            if chat_id is not None:
                await safe_send_message(
                    bot=bot,
                    chat_id=int(chat_id),
                    text=text,
                    reply_markup=_subscription_keyboard(int(user_id)),
                    reply_to_message_id=reply_to_message_id,
                )
        except Exception:
            pass

        return None


fallback_router = Router()
subscription_router = Router()


def _moscow_tzinfo():
    if ZoneInfo is not None:
        try:
            return ZoneInfo("Europe/Moscow")
        except Exception:
            pass
    return timezone(timedelta(hours=3))


async def _bitcoin_rate_hourly_refresh_task() -> None:
    tz = _moscow_tzinfo()
                                     
    try:
        trigger_bitcoin_rate_refresh(force=True)
    except Exception:
        pass

    while True:
        now = datetime.now(tz)
        next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        delay = (next_hour - now).total_seconds()
        if delay < 1.0:
            delay = 1.0
        await asyncio.sleep(delay)
        try:
            trigger_bitcoin_rate_refresh(force=True)
        except Exception:
            pass


async def _db_backup_once(bot: Bot) -> None:
    chat_id = int(DB_BACKUP_CHAT_ID or 0)
    if chat_id == 0:
        return

    def _do_backup_to_file(dst_path: str) -> None:
        src_path = ""
        try:
            row = db.cursor.execute("PRAGMA database_list").fetchone()
            if row is not None:
                src_path = str(row[2] or "")
        except Exception:
            src_path = ""

        if not src_path:
            src_path = os.path.abspath("mining_farm.db")
        else:
            src_path = os.path.abspath(src_path)

        src_conn = sqlite3.connect(src_path, timeout=30)
        try:
            dst_conn = sqlite3.connect(dst_path)
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
        finally:
            src_conn.close()

    try:
        tz = _moscow_tzinfo()
        now = datetime.now(tz)
        ts_str = now.strftime("%Y-%m-%d_%H-%M-%S")
        with tempfile.TemporaryDirectory(prefix="mf_db_backup_") as tmpdir:
            backup_path = os.path.join(tmpdir, f"mining_farm_backup_{ts_str}.db")
            await asyncio.to_thread(_do_backup_to_file, backup_path)

            size_bytes = 0
            try:
                size_bytes = int(os.path.getsize(backup_path))
            except Exception:
                size_bytes = 0

            users_cnt = 0
            clans_cnt = 0
            try:
                users_cnt = int((db.cursor.execute("SELECT COUNT(*) FROM users").fetchone() or [0])[0] or 0)
            except Exception:
                users_cnt = 0
            try:
                clans_cnt = int((db.cursor.execute("SELECT COUNT(*) FROM clans").fetchone() or [0])[0] or 0)
            except Exception:
                clans_cnt = 0

            caption = (
                f"🗄 <b>Бэкап базы данных</b>\n"
                f"📅 <b>Дата:</b> {now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                f"👥 <b>Пользователей:</b> {users_cnt}\n"
                f"🏴 <b>Кланов:</b> {clans_cnt}\n"
                f"📦 <b>Размер:</b> {size_bytes / (1024 * 1024):.2f} MB"
            )

            await bot.send_document(
                chat_id=chat_id,
                document=FSInputFile(backup_path),
                caption=caption,
                parse_mode="HTML",
            )
    except Exception:
        logger.exception("DB backup task failed")


async def _db_backup_halfhour_task(bot: Bot) -> None:
    tz = _moscow_tzinfo()
    while True:
        now = datetime.now(tz)
                                         
        if now.minute < 30:
            target = now.replace(minute=30, second=0, microsecond=0)
        else:
            target = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        delay = (target - now).total_seconds()
        if delay < 1.0:
            delay = 1.0
        await asyncio.sleep(delay)
        await _db_backup_once(bot)


@fallback_router.callback_query()
async def _unknown_callback_query(callback: CallbackQuery):
    try:
        await callback.answer("ℹ️ Кнопка устарела. Откройте меню заново.")
    except Exception:
        pass


@subscription_router.callback_query(F.data.startswith(CHECK_SUB_CALLBACK))
async def _check_news_subscription(callback: CallbackQuery):
    data = callback.data or ""
    owner_id: int | None = None
    if data == CHECK_SUB_CALLBACK:
        owner_id = None
    else:
        try:
            owner_id = int(data.split("_", maxsplit=3)[-1])
        except Exception:
            owner_id = None

    user_id = int(callback.from_user.id)
    if owner_id is not None and int(owner_id) != user_id:
        await callback.answer("❌ Это не ваша кнопка.", show_alert=True)
        return
    if owner_id is None and callback.message is not None and callback.message.chat is not None:
        if callback.message.chat.type in ("group", "supergroup"):
            await callback.answer("ℹ️ Кнопка устарела. Откройте меню заново.", show_alert=True)
            return

    ok = await _is_user_subscribed(callback.bot, int(user_id), force_refresh=True)
    if not ok:
        await asyncio.sleep(1)
        ok = await _is_user_subscribed(callback.bot, int(user_id), force_refresh=True)
    if ok:
        await callback.answer("✅ Подписка подтверждена. Можете пользоваться ботом.", show_alert=True)
        try:
            msg = callback.message
            if msg is not None and msg.chat is not None:
                await safe_edit_message_text(
                    bot=callback.bot,
                    chat_id=int(msg.chat.id),
                    message_id=int(msg.message_id),
                    text=(
                        "✅ <b>Подписка подтверждена</b>\n\n"
                        "Теперь можно пользоваться ботом в этом чате."
                    ),
                    reply_markup=None,
                    parse_mode="HTML",
                )
        except Exception:
            pass
        return
    await callback.answer("❌ Подписка не найдена. Подпишитесь и нажмите ещё раз.", show_alert=True)


async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен! Создайте файл .env с BOT_TOKEN=your_token_here")
        return
    
                                     
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    dp.update.middleware(BanIgnoreMiddleware())
    dp.message.middleware(GroupOnlyMiddleware())
    dp.callback_query.middleware(GroupOnlyMiddleware())
    dp.message.middleware(BanIgnoreMiddleware())
    dp.callback_query.middleware(BanIgnoreMiddleware())

    dp.message.middleware(SubscriptionMiddleware())
                                                                              
    
                                    
                                                                     
                                                                      
    
                               
    dp.include_router(subscription_router)
    dp.include_router(start.router)
    dp.include_router(shop.router)
    dp.include_router(mining.router)
    dp.include_router(wallet.router)
    dp.include_router(inventory.router)
    dp.include_router(equipment.router)
    dp.include_router(admin.router)
    dp.include_router(category_images.router)
    dp.include_router(leaderboard.router)
    dp.include_router(report.router)
    dp.include_router(transfer.router)
    dp.include_router(profile.router)
    dp.include_router(clans.router)
    dp.include_router(synapse.router)
    dp.include_router(wiki.router)
    dp.include_router(info.router)
    dp.include_router(fallback_router)

    logger.info("Бот запущен и готов к работе!")

    btc_refresh_task = asyncio.create_task(_bitcoin_rate_hourly_refresh_task())
    db_backup_task = None
    if int(DB_BACKUP_CHAT_ID or 0) != 0:
        db_backup_task = asyncio.create_task(_db_backup_halfhour_task(bot))
    
                                                                     
                                         
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.warning(f"Не удалось удалить webhook: {e}")
    
                                                                               
    backoff_s = 1.0
    try:
        while True:
            try:
                await dp.start_polling(bot, skip_updates=True)
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Polling crashed; restarting in %.1f seconds", backoff_s)
                await asyncio.sleep(backoff_s)
                backoff_s = min(backoff_s * 2.0, 30.0)
    finally:
        btc_refresh_task.cancel()
        if db_backup_task is not None:
            db_backup_task.cancel()
        try:
            await btc_refresh_task
        except BaseException:
            pass
        if db_backup_task is not None:
            try:
                await db_backup_task
            except BaseException:
                pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

