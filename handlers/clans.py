from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.filters import BaseFilter
from database import db
from utils import (
    check_user_banned,
    save_chat_from_message,
    save_chat_from_callback,
    check_message_owner,
    handle_unauthorized_access,
    safe_edit_message_text,
    render_ui_from_callback,
    render_ui_from_message,
    set_ui_key_for_message,
)
from keyboards import get_back_to_farm_keyboard, get_clans_keyboard
import html


router = Router()


CLAN_CREATE_COST_USD = 5_000_000
CLAN_INVITE_ACCEPT_PREFIX = "clan_invite_accept_"


def _extract_owner_id_from_callback_data(callback: CallbackQuery, prefix: str) -> int | None:
    data = (callback.data or "").strip()
    if not data.startswith(prefix):
        return None

    suffix = data[len(prefix) :]
    try:
        return int(suffix)
    except Exception:
        pass

    for part in reversed(data.split("_")):
        try:
            return int(part)
        except Exception:
            continue

    if callback.from_user is not None:
        try:
            return int(callback.from_user.id)
        except Exception:
            return None

    return None


_awaiting_clan_treasury: dict[int, dict[str, object]] = {}


_awaiting_clan_manage: dict[int, dict[str, object]] = {}


class _AwaitingClanTreasuryFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if message.from_user is None:
            return False
        return int(message.from_user.id) in _awaiting_clan_treasury


class _AwaitingClanManageFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if message.from_user is None:
            return False
        return int(message.from_user.id) in _awaiting_clan_manage


def _format_event_row(event: dict) -> str:
    et = str(event.get("event_type") or "")
    actor = event.get("actor_user_id")
    amount = event.get("amount_usd")
    meta = event.get("meta")
    ts = event.get("created_at")

    actor_text = f"<code>{int(actor)}</code>" if actor else "—"
    amount_text = f"{float(amount):.2f} USD" if amount is not None else ""

    if et == "clan_created":
        label = "🏁 Клан создан"
    elif et == "member_join":
        label = "✅ Вступление"
    elif et == "treasury_deposit":
        label = "💰 Пополнение казны"
    elif et == "treasury_withdraw":
        label = "🏧 Вывод из казны"
    elif et == "bonus_purchase":
        label = "🛒 Покупка бонуса"
    elif et == "member_leave":
        label = "🚪 Выход из клана"
    elif et == "member_kick":
        label = "👢 Исключение участника"
    elif et == "leader_transfer":
        label = "👑 Передача лидерства"
    elif et == "clan_disband":
        label = "🧨 Роспуск клана"
    else:
        label = html.escape(et)

    meta_text = ""
    if meta:
        meta_text = f" ({html.escape(str(meta))})"

    ts_text = html.escape(str(ts)) if ts else ""
    details = " ".join([p for p in [actor_text, amount_text] if p]).strip()
    if details:
        details = " — " + details
    if ts_text:
        ts_text = f"\n   ⏱ {ts_text}"
    return f"• {label}{meta_text}{details}{ts_text}"


def _clans_simple_back_kb(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к клану", callback_data=f"main_clans_{owner_id}")],
            [InlineKeyboardButton(text="🔙 Назад к ферме", callback_data=f"back_to_farm_{owner_id}")],
        ]
    )


def _clans_treasury_kb(owner_id: int, is_leader: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="➕ Пополнить", callback_data=f"clans_treasury_deposit_{owner_id}"),
        ]
    ]
    if is_leader:
        rows.append(
            [
                InlineKeyboardButton(text="➖ Вывести", callback_data=f"clans_treasury_withdraw_{owner_id}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="🔙 Назад к клану", callback_data=f"main_clans_{owner_id}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад к ферме", callback_data=f"back_to_farm_{owner_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _render_clan_treasury_view(bot, chat_id: int, message_id: int, owner_id: int) -> None:
    clan = db.get_clan_for_user(int(owner_id))
    if not clan:
        return

    clan_id = int(clan.get("clan_id") or 0)
    is_leader = str(clan.get("member_role")) == "leader"
    name = html.escape(str(clan.get("name") or ""))

    db.cursor.execute("SELECT treasury_usd FROM clans WHERE clan_id = ?", (clan_id,))
    row = db.cursor.fetchone()
    treasury = float((row["treasury_usd"] if row else 0) or 0)

    text = (
        "💰 <b>Казна клана</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏷 <b>Клан:</b> {name}\n"
        f"🆔 <b>ID:</b> <code>{clan_id}</code>\n"
        f"💵 <b>В казне:</b> {treasury:.2f} USD\n\n"
        "➕ Пополнять казну может любой участник.\n"
        "➖ Вывод доступен только главе клана."
    )

    set_ui_key_for_message(int(chat_id), int(owner_id), int(message_id), "clans")
    await safe_edit_message_text(
        bot=bot,
        chat_id=int(chat_id),
        message_id=int(message_id),
        text=text,
        reply_markup=_clans_treasury_kb(owner_id, is_leader=is_leader),
        parse_mode="HTML",
    )


async def _render_clan_members_view(bot, chat_id: int, message_id: int, owner_id: int) -> None:
    clan = db.get_clan_for_user(int(owner_id))
    if not clan:
        return

    clan_id = int(clan.get("clan_id") or 0)
    is_leader = str(clan.get("member_role")) == "leader"
    name = html.escape(str(clan.get("name") or ""))
    members = db.get_clan_members(clan_id)

    lines: list[str] = []
    lines.append("👥 <b>Участники клана</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━\n")
    lines.append(f"🏷 <b>Клан:</b> {name}")
    lines.append("")

    for m in members:
        uid = int(m.get("user_id") or 0)
        role = str(m.get("role") or "member")
        uname = (m.get("username") or "").strip()
        uname_text = f"@{html.escape(uname)}" if uname else ""
        role_text = "👑 лидер" if role == "leader" else "👤 участник"
        tail = f" {uname_text}" if uname_text else ""
        lines.append(f"• <code>{uid}</code> — {role_text}{tail}")

    if is_leader:
        lines.append("\n<b>Управление:</b>")
        lines.append("• 👢 Кик — выберите кнопку и введите user_id")
        lines.append("• 👑 Передача лидерства — выберите кнопку и введите user_id")
    else:
        lines.append("\nℹ️ Управлять составом может только лидер.")

    text = "\n".join(lines).rstrip()

    rows: list[list[InlineKeyboardButton]] = []
    if is_leader:
        rows.append(
            [
                InlineKeyboardButton(text="👢 Кикнуть", callback_data=f"clans_manage_kick_{owner_id}"),
                InlineKeyboardButton(text="👑 Передать лидерство", callback_data=f"clans_manage_transfer_{owner_id}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="🔙 Назад к клану", callback_data=f"main_clans_{owner_id}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад к ферме", callback_data=f"back_to_farm_{owner_id}")])

    set_ui_key_for_message(int(chat_id), int(owner_id), int(message_id), "clans")
    await safe_edit_message_text(
        bot=bot,
        chat_id=int(chat_id),
        message_id=int(message_id),
        text=text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )


def _clans_shop_kb(owner_id: int, is_leader: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if is_leader:
        rows.append(
            [
                InlineKeyboardButton(text="⚡ +10% (24ч)", callback_data=f"clans_shop_buy_hashrate10_24h_{owner_id}"),
                InlineKeyboardButton(text="⚡ +25% (24ч)", callback_data=f"clans_shop_buy_hashrate25_24h_{owner_id}"),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(text="⚡ +10% (72ч)", callback_data=f"clans_shop_buy_hashrate10_72h_{owner_id}"),
                InlineKeyboardButton(text="⚡ +25% (72ч)", callback_data=f"clans_shop_buy_hashrate25_72h_{owner_id}"),
            ]
        )

    rows.append([InlineKeyboardButton(text="🔙 Назад к клану", callback_data=f"main_clans_{owner_id}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад к ферме", callback_data=f"back_to_farm_{owner_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("main_clans_"))
async def main_clans_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)

    try:
        owner_id = int((callback.data or "").replace("main_clans_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    is_owner, _user_id = check_message_owner(callback, owner_id)
    if not is_owner:
        await handle_unauthorized_access(callback)
        return

    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await callback.answer(
            f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}",
            show_alert=True,
        )
        return

    clan = db.get_clan_for_user(int(owner_id))
    if clan:
        clan_id = int(clan.get("clan_id") or 0)
        name = html.escape(str(clan.get("name") or ""))
        leader_id = int(clan.get("leader_id") or 0)
        role = html.escape(str(clan.get("member_role") or "member"))
        members = db.get_clan_member_count(clan_id)
        text = (
            "🏴 <b>Кланы</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏷 <b>Ваш клан:</b> {name}\n"
            f"🆔 <b>ID:</b> <code>{clan_id}</code>\n"
            f"👑 <b>Глава:</b> <code>{leader_id}</code>\n"
            f"👥 <b>Участников:</b> {members}\n"
            f"🎭 <b>Ваша роль:</b> {role}\n\n"
            "📨 <b>Приглашение:</b> ответьте на сообщение игрока и напишите\n"
            "<code>Отправить приглашение</code>\n"
            "или команду <code>/clan_invite</code>."
        )
    else:
        text = (
            "🏴 <b>Кланы</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🏳️ Вы пока не состоите в клане.\n\n"
            "Создать клан:\n"
            f"<code>/clan_create &lt;название&gt;</code>\n"
            f"Стоимость: <b>{CLAN_CREATE_COST_USD:,}</b> USD".replace(",", " ")
        )

    await callback.answer()

    if callback.message is None or callback.message.chat is None:
        return
    set_ui_key_for_message(
        int(callback.message.chat.id),
        int(owner_id),
        int(callback.message.message_id),
        "clans",
    )

    clans_file_id = (db.get_setting("ui_image_clans", "") or "").strip()
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=text,
        reply_markup=get_clans_keyboard(int(owner_id), has_clan=bool(clan), is_leader=(str(clan.get("member_role")) == "leader") if clan else False),
        parse_mode="HTML",
        ui_key="clans",
        photo=(clans_file_id if clans_file_id else ""),
    )


@router.callback_query(F.data.startswith("clans_create_hint_"))
async def clans_create_hint_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)

    try:
        owner_id = int((callback.data or "").replace("clans_create_hint_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    is_owner, _user_id = check_message_owner(callback, owner_id)
    if not is_owner:
        await handle_unauthorized_access(callback)
        return

    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await callback.answer(
            f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}",
            show_alert=True,
        )
        return

    text = (
        "🏴 <b>Кланы — создание</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Создать клан:\n"
        "<code>/clan_create &lt;название&gt;</code>\n\n"
        f"Стоимость: <b>{CLAN_CREATE_COST_USD:,}</b> USD".replace(",", " ")
    )

    await callback.answer()
    if callback.message is None or callback.message.chat is None:
        return

    set_ui_key_for_message(
        int(callback.message.chat.id),
        int(owner_id),
        int(callback.message.message_id),
        "clans",
    )

    clans_file_id = (db.get_setting("ui_image_clans", "") or "").strip()
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=text,
        reply_markup=get_clans_keyboard(int(owner_id), has_clan=False),
        parse_mode="HTML",
        ui_key="clans",
        photo=(clans_file_id if clans_file_id else ""),
    )


@router.callback_query(F.data.startswith("clans_invite_hint_"))
async def clans_invite_hint_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)

    try:
        owner_id = int((callback.data or "").replace("clans_invite_hint_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    is_owner, _user_id = check_message_owner(callback, owner_id)
    if not is_owner:
        await handle_unauthorized_access(callback)
        return

    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await callback.answer(
            f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}",
            show_alert=True,
        )
        return

    text = (
        "🏴 <b>Кланы — приглашение</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Чтобы пригласить игрока в клан:\n"
        "1) Ответьте на сообщение игрока\n"
        "2) Напишите: <code>/clan_invite</code>\n\n"
        "Также можно написать: <code>Отправить приглашение</code> (ответом)."
    )

    clan = db.get_clan_for_user(int(owner_id))
    await callback.answer()
    if callback.message is None or callback.message.chat is None:
        return

    set_ui_key_for_message(
        int(callback.message.chat.id),
        int(owner_id),
        int(callback.message.message_id),
        "clans",
    )

    clans_file_id = (db.get_setting("ui_image_clans", "") or "").strip()
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=text,
        reply_markup=get_clans_keyboard(int(owner_id), has_clan=bool(clan), is_leader=(str(clan.get("member_role")) == "leader") if clan else False),
        parse_mode="HTML",
        ui_key="clans",
        photo=(clans_file_id if clans_file_id else ""),
    )


@router.callback_query(
    lambda c: (c.data or "").startswith("clans_treasury_")
    and (c.data or "")[len("clans_treasury_") :].isdigit()
)
async def clans_treasury_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)

    owner_id = _extract_owner_id_from_callback_data(callback, "clans_treasury_")
    if owner_id is None:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    is_owner, _user_id = check_message_owner(callback, owner_id)
    if not is_owner:
        await handle_unauthorized_access(callback)
        return

    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await callback.answer(f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}", show_alert=True)
        return

    clan = db.get_clan_for_user(int(owner_id))
    if not clan:
        await callback.answer("❌ Вы не состоите в клане.", show_alert=True)
        return

    clan_id = int(clan.get("clan_id") or 0)
    is_leader = str(clan.get("member_role")) == "leader"
    name = html.escape(str(clan.get("name") or ""))

    db.cursor.execute("SELECT treasury_usd FROM clans WHERE clan_id = ?", (clan_id,))
    row = db.cursor.fetchone()
    treasury = float((row["treasury_usd"] if row else 0) or 0)

    text = (
        "💰 <b>Казна клана</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏷 <b>Клан:</b> {name}\n"
        f"🆔 <b>ID:</b> <code>{clan_id}</code>\n"
        f"💵 <b>В казне:</b> {treasury:.2f} USD\n\n"
        "➕ Пополнять казну может любой участник.\n"
        "➖ Вывод доступен только главе клана."
    )

    await callback.answer()
    if callback.message is None or callback.message.chat is None:
        return

    set_ui_key_for_message(int(callback.message.chat.id), int(owner_id), int(callback.message.message_id), "clans")
    clans_file_id = (db.get_setting("ui_image_clans", "") or "").strip()
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=text,
        reply_markup=_clans_treasury_kb(owner_id, is_leader=is_leader),
        parse_mode="HTML",
        ui_key="clans",
        photo=(clans_file_id if clans_file_id else ""),
    )


@router.callback_query(F.data.startswith("clans_treasury_deposit_"))
async def clans_treasury_deposit_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)

    owner_id = _extract_owner_id_from_callback_data(callback, "clans_treasury_deposit_")
    if owner_id is None:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    is_owner, _user_id = check_message_owner(callback, owner_id)
    if not is_owner:
        await handle_unauthorized_access(callback)
        return

    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await callback.answer(f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}", show_alert=True)
        return

    user = db.get_user(owner_id)
    if not user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    balance = float(user.get("balance", 0) or 0)

    if callback.message is not None:
        _awaiting_clan_treasury[owner_id] = {
            "action": "deposit",
            "chat_id": int(callback.message.chat.id),
            "message_id": int(callback.message.message_id),
        }
    else:
        _awaiting_clan_treasury[owner_id] = {"action": "deposit"}

    await callback.answer()
    if callback.message is None or callback.message.chat is None:
        return

    set_ui_key_for_message(int(callback.message.chat.id), int(owner_id), int(callback.message.message_id), "clans")

    prompt_text = (
        "➕ <b>Пополнение казны</b>\n\n"
        "Введите сумму в USD для пополнения.\n\n"
        "Можно написать <code>all</code> — чтобы перевести весь баланс.\n"
        "Для отмены напишите <code>cancel</code>.\n\n"
        f"Доступно: <b>{balance:.2f} USD</b>"
    )

    await safe_edit_message_text(
        bot=callback.bot,
        chat_id=int(callback.message.chat.id),
        message_id=int(callback.message.message_id),
        text=prompt_text,
        reply_markup=_clans_simple_back_kb(owner_id),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("clans_treasury_withdraw_"))
async def clans_treasury_withdraw_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)

    owner_id = _extract_owner_id_from_callback_data(callback, "clans_treasury_withdraw_")
    if owner_id is None:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    is_owner, _user_id = check_message_owner(callback, owner_id)
    if not is_owner:
        await handle_unauthorized_access(callback)
        return

    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await callback.answer(f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}", show_alert=True)
        return

    clan = db.get_clan_for_user(int(owner_id))
    if not clan:
        await callback.answer("❌ Вы не состоите в клане.", show_alert=True)
        return

    if str(clan.get("member_role")) != "leader":
        await callback.answer("❌ Выводить средства может только глава клана.", show_alert=True)
        return

    clan_id = int(clan.get("clan_id") or 0)
    db.cursor.execute("SELECT treasury_usd FROM clans WHERE clan_id = ?", (clan_id,))
    row = db.cursor.fetchone()
    treasury = float((row["treasury_usd"] if row else 0) or 0)

    if callback.message is not None:
        _awaiting_clan_treasury[owner_id] = {
            "action": "withdraw",
            "chat_id": int(callback.message.chat.id),
            "message_id": int(callback.message.message_id),
        }
    else:
        _awaiting_clan_treasury[owner_id] = {"action": "withdraw"}

    await callback.answer()
    if callback.message is None or callback.message.chat is None:
        return

    set_ui_key_for_message(int(callback.message.chat.id), int(owner_id), int(callback.message.message_id), "clans")

    prompt_text = (
        "➖ <b>Вывод из казны</b>\n\n"
        "Введите сумму в USD для вывода на ваш баланс.\n\n"
        "Можно написать <code>all</code> — чтобы вывести всё.\n"
        "Для отмены напишите <code>cancel</code>.\n\n"
        f"Доступно в казне: <b>{treasury:.2f} USD</b>"
    )

    await safe_edit_message_text(
        bot=callback.bot,
        chat_id=int(callback.message.chat.id),
        message_id=int(callback.message.message_id),
        text=prompt_text,
        reply_markup=_clans_simple_back_kb(owner_id),
        parse_mode="HTML",
    )


@router.message(_AwaitingClanTreasuryFilter(), F.text)
async def clans_treasury_amount_message(message: Message):
    owner_id = int(message.from_user.id)
    ctx = _awaiting_clan_treasury.pop(owner_id, {})

    text = (message.text or "").strip()
    text_l = text.lower()
    if text_l in ("cancel", "отмена"):
        await message.answer("ℹ️ Операция отменена.")
        return

    clan = db.get_clan_for_user(owner_id)
    if not clan:
        await message.answer("❌ Вы не состоите в клане.")
        return

    action = str(ctx.get("action") or "")
    clan_id = int(clan.get("clan_id") or 0)

    if text_l == "all":
        if action == "deposit":
            user = db.get_user(owner_id) or {}
            amount = float(user.get("balance", 0) or 0)
        else:
            db.cursor.execute("SELECT treasury_usd FROM clans WHERE clan_id = ?", (clan_id,))
            row = db.cursor.fetchone()
            amount = float((row["treasury_usd"] if row else 0) or 0)
    else:
        try:
            amount = float(text.replace(",", "."))
        except ValueError:
            await message.answer("❌ Неверное значение. Напишите число или <code>all</code>.", parse_mode="HTML")
            return

    if amount <= 0:
        await message.answer("❌ Сумма должна быть больше нуля.")
        return

    if action == "deposit":
        ok, msg, _new_treasury = db.clan_deposit_to_treasury(owner_id, amount)
    else:
        ok, msg, _new_treasury = db.clan_withdraw_from_treasury(owner_id, amount)

    await message.answer(msg, parse_mode="HTML")

    chat_id = ctx.get("chat_id")
    message_id = ctx.get("message_id")
    if chat_id and message_id:
        try:
            await _render_clan_treasury_view(message.bot, int(chat_id), int(message_id), owner_id)
        except Exception:
            pass


@router.callback_query(F.data.startswith("clans_members_"))
async def clans_members_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)

    try:
        owner_id = int((callback.data or "").replace("clans_members_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    is_owner, _user_id = check_message_owner(callback, owner_id)
    if not is_owner:
        await handle_unauthorized_access(callback)
        return

    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await callback.answer(f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}", show_alert=True)
        return

    clan = db.get_clan_for_user(int(owner_id))
    if not clan:
        await callback.answer("❌ Вы не состоите в клане.", show_alert=True)
        return

    await callback.answer()
    if callback.message is None or callback.message.chat is None:
        return

    await _render_clan_members_view(callback.bot, int(callback.message.chat.id), int(callback.message.message_id), owner_id)


@router.callback_query(F.data.startswith("clans_manage_kick_"))
async def clans_manage_kick_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)

    try:
        owner_id = int((callback.data or "").replace("clans_manage_kick_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    is_owner, _user_id = check_message_owner(callback, owner_id)
    if not is_owner:
        await handle_unauthorized_access(callback)
        return

    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await callback.answer(f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}", show_alert=True)
        return

    clan = db.get_clan_for_user(int(owner_id))
    if not clan or str(clan.get("member_role")) != "leader":
        await callback.answer("❌ Доступно только главе клана.", show_alert=True)
        return

    if callback.message is not None:
        _awaiting_clan_manage[owner_id] = {
            "action": "kick",
            "chat_id": int(callback.message.chat.id),
            "message_id": int(callback.message.message_id),
        }
    else:
        _awaiting_clan_manage[owner_id] = {"action": "kick"}

    await callback.answer()
    if callback.message is None or callback.message.chat is None:
        return

    set_ui_key_for_message(int(callback.message.chat.id), int(owner_id), int(callback.message.message_id), "clans")
    await safe_edit_message_text(
        bot=callback.bot,
        chat_id=int(callback.message.chat.id),
        message_id=int(callback.message.message_id),
        text=(
            "👢 <b>Кик участника</b>\n\n"
            "Введите <code>user_id</code> участника, которого нужно исключить.\n"
            "Для отмены напишите <code>cancel</code>."
        ),
        reply_markup=_clans_simple_back_kb(owner_id),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("clans_manage_transfer_"))
async def clans_manage_transfer_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)

    try:
        owner_id = int((callback.data or "").replace("clans_manage_transfer_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    is_owner, _user_id = check_message_owner(callback, owner_id)
    if not is_owner:
        await handle_unauthorized_access(callback)
        return

    clan = db.get_clan_for_user(int(owner_id))
    if not clan or str(clan.get("member_role")) != "leader":
        await callback.answer("❌ Доступно только главе клана.", show_alert=True)
        return

    if callback.message is not None:
        _awaiting_clan_manage[owner_id] = {
            "action": "transfer",
            "chat_id": int(callback.message.chat.id),
            "message_id": int(callback.message.message_id),
        }
    else:
        _awaiting_clan_manage[owner_id] = {"action": "transfer"}

    await callback.answer()
    if callback.message is None or callback.message.chat is None:
        return

    set_ui_key_for_message(int(callback.message.chat.id), int(owner_id), int(callback.message.message_id), "clans")
    await safe_edit_message_text(
        bot=callback.bot,
        chat_id=int(callback.message.chat.id),
        message_id=int(callback.message.message_id),
        text=(
            "👑 <b>Передача лидерства</b>\n\n"
            "Введите <code>user_id</code> участника, которому хотите передать лидерство.\n"
            "Для отмены напишите <code>cancel</code>."
        ),
        reply_markup=_clans_simple_back_kb(owner_id),
        parse_mode="HTML",
    )


@router.message(_AwaitingClanManageFilter(), F.text)
async def clans_manage_message(message: Message):
    owner_id = int(message.from_user.id)
    ctx = _awaiting_clan_manage.pop(owner_id, {})

    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await message.answer(
            f"🚫 <b>Ваш аккаунт заблокирован!</b>\n\n📋 <b>Причина:</b> {html.escape(ban_reason or '')}",
            parse_mode="HTML",
        )
        return

    text = (message.text or "").strip()
    text_l = text.lower()
    if text_l in ("cancel", "отмена"):
        await message.answer("ℹ️ Операция отменена.")
        return

    try:
        target_id = int(text)
    except ValueError:
        await message.answer("❌ Введите числовой user_id.")
        return

    action = str(ctx.get("action") or "")
    if action == "kick":
        ok, msg = db.kick_clan_member(owner_id, target_id)
    else:
        ok, msg = db.transfer_clan_leadership(owner_id, target_id)

    await message.answer(msg, parse_mode="HTML")

    chat_id = ctx.get("chat_id")
    message_id = ctx.get("message_id")
    if chat_id and message_id:
        try:
            await _render_clan_members_view(message.bot, int(chat_id), int(message_id), owner_id)
        except Exception:
            pass


@router.callback_query(F.data.startswith("clans_leave_"))
async def clans_leave_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)

    try:
        owner_id = int((callback.data or "").replace("clans_leave_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    is_owner, _user_id = check_message_owner(callback, owner_id)
    if not is_owner:
        await handle_unauthorized_access(callback)
        return

    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await callback.answer(f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}", show_alert=True)
        return

    ok, msg = db.leave_clan(owner_id)
    await callback.answer(msg, show_alert=True)
    await main_clans_handler(callback)


@router.callback_query(
    lambda c: (c.data or "").startswith("clans_disband_")
    and (c.data or "")[len("clans_disband_") :].isdigit()
)
async def clans_disband_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)

    owner_id = _extract_owner_id_from_callback_data(callback, "clans_disband_")
    if owner_id is None:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    is_owner, _user_id = check_message_owner(callback, owner_id)
    if not is_owner:
        await handle_unauthorized_access(callback)
        return

    clan = db.get_clan_for_user(int(owner_id))
    if not clan or str(clan.get("member_role")) != "leader":
        await callback.answer("❌ Доступно только главе клана.", show_alert=True)
        return

    await callback.answer()
    if callback.message is None or callback.message.chat is None:
        return

    set_ui_key_for_message(int(callback.message.chat.id), int(owner_id), int(callback.message.message_id), "clans")
    confirm_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить роспуск", callback_data=f"clans_disband_confirm_{owner_id}"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"main_clans_{owner_id}"),
            ],
        ]
    )
    await safe_edit_message_text(
        bot=callback.bot,
        chat_id=int(callback.message.chat.id),
        message_id=int(callback.message.message_id),
        text=(
            "🧨 <b>Роспуск клана</b>\n\n"
            "Вы уверены, что хотите распустить клан?\n"
            "Это действие удалит клан и всех участников из него."
        ),
        reply_markup=confirm_kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("clans_disband_confirm_"))
async def clans_disband_confirm_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)

    try:
        owner_id = int((callback.data or "").replace("clans_disband_confirm_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    is_owner, _user_id = check_message_owner(callback, owner_id)
    if not is_owner:
        await handle_unauthorized_access(callback)
        return

    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await callback.answer(f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}", show_alert=True)
        return

    clan = db.get_clan_for_user(int(owner_id))
    if not clan or str(clan.get("member_role")) != "leader":
        await callback.answer("❌ Доступно только главе клана.", show_alert=True)
        return

    ok, msg = db.disband_clan(owner_id)
    await callback.answer(msg, show_alert=True)
    await main_clans_handler(callback)


@router.callback_query(F.data.startswith("clans_events_"))
async def clans_events_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)

    try:
        owner_id = int((callback.data or "").replace("clans_events_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    is_owner, _user_id = check_message_owner(callback, owner_id)
    if not is_owner:
        await handle_unauthorized_access(callback)
        return

    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await callback.answer(f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}", show_alert=True)
        return

    clan = db.get_clan_for_user(int(owner_id))
    if not clan:
        await callback.answer("❌ Вы не состоите в клане.", show_alert=True)
        return

    clan_id = int(clan.get("clan_id") or 0)
    name = html.escape(str(clan.get("name") or ""))
    events = db.get_clan_events(clan_id, limit=20)

    lines: list[str] = []
    lines.append("🧾 <b>Лог клана</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━\n")
    lines.append(f"🏷 <b>Клан:</b> {name}")
    lines.append("")

    if not events:
        lines.append("ℹ️ Событий пока нет.")
    else:
        for e in events:
            lines.append(_format_event_row(e))

    text = "\n".join(lines).rstrip()

    await callback.answer()
    if callback.message is None or callback.message.chat is None:
        return

    set_ui_key_for_message(int(callback.message.chat.id), int(owner_id), int(callback.message.message_id), "clans")
    clans_file_id = (db.get_setting("ui_image_clans", "") or "").strip()
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=text,
        reply_markup=_clans_simple_back_kb(owner_id),
        parse_mode="HTML",
        ui_key="clans",
        photo=(clans_file_id if clans_file_id else ""),
    )


@router.callback_query(
    lambda c: (c.data or "").startswith("clans_shop_")
    and (c.data or "")[len("clans_shop_") :].isdigit()
)
async def clans_shop_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)

    owner_id = _extract_owner_id_from_callback_data(callback, "clans_shop_")
    if owner_id is None:
        owner_id = _extract_owner_id_from_callback_data(callback, "")
    if owner_id is None:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    is_owner, _user_id = check_message_owner(callback, owner_id)
    if not is_owner:
        await handle_unauthorized_access(callback)
        return

    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await callback.answer(f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}", show_alert=True)
        return

    clan = db.get_clan_for_user(int(owner_id))
    if not clan:
        await callback.answer("❌ Вы не состоите в клане.", show_alert=True)
        return

    clan_id = int(clan.get("clan_id") or 0)
    is_leader = str(clan.get("member_role")) == "leader"
    name = html.escape(str(clan.get("name") or ""))

    db.cursor.execute("SELECT treasury_usd FROM clans WHERE clan_id = ?", (clan_id,))
    row = db.cursor.fetchone()
    treasury = float((row["treasury_usd"] if row else 0) or 0)
    active = db.get_clan_active_bonuses(clan_id, limit=10)
    total_percent = db.get_clan_hashrate_bonus_percent(clan_id)

    lines: list[str] = []
    lines.append("🛒 <b>Магазин клана</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━\n")
    lines.append(f"🏷 <b>Клан:</b> {name}")
    lines.append(f"💵 <b>В казне:</b> {treasury:.2f} USD")
    lines.append("")
    lines.append(f"⚡ <b>Активный бонус хешрейта:</b> +{total_percent * 100:.0f}%")
    if active:
        lines.append("\n<b>Активные бонусы:</b>")
        for b in active:
            bkey = html.escape(str(b.get("bonus_key") or ""))
            pct = float(b.get("percent") or 0) * 100.0
            exp = html.escape(str(b.get("expires_at") or ""))
            lines.append(f"• {bkey}: +{pct:.0f}% до {exp}")
    else:
        lines.append("\nℹ️ Активных бонусов нет.")

    lines.append("\n<b>Доступные бонусы (оплата из казны):</b>")
    lines.append("• ⚡ +10% на 24ч — 50 000 USD")
    lines.append("• ⚡ +25% на 24ч — 110 000 USD")
    lines.append("• ⚡ +10% на 72ч — 130 000 USD")
    lines.append("• ⚡ +25% на 72ч — 300 000 USD")
    if not is_leader:
        lines.append("\nℹ️ Покупать бонусы может только глава клана.")

    text = "\n".join(lines).rstrip()

    await callback.answer()
    if callback.message is None or callback.message.chat is None:
        return

    set_ui_key_for_message(int(callback.message.chat.id), int(owner_id), int(callback.message.message_id), "clans")
    clans_file_id = (db.get_setting("ui_image_clans", "") or "").strip()
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=text,
        reply_markup=_clans_shop_kb(owner_id, is_leader=is_leader),
        parse_mode="HTML",
        ui_key="clans",
        photo=(clans_file_id if clans_file_id else ""),
    )


@router.callback_query(F.data.startswith("clans_shop_buy_"))
async def clans_shop_buy_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
    data = callback.data or ""

    try:
        rest = data.replace("clans_shop_buy_", "")
        bonus_key, owner_raw = rest.rsplit("_", maxsplit=1)
        owner_id = int(owner_raw)
    except Exception:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    is_owner, _user_id = check_message_owner(callback, owner_id)
    if not is_owner:
        await handle_unauthorized_access(callback)
        return

    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await callback.answer(f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}", show_alert=True)
        return

    clan = db.get_clan_for_user(int(owner_id))
    if not clan:
        await callback.answer("❌ Вы не состоите в клане.", show_alert=True)
        return

    if str(clan.get("member_role")) != "leader":
        await callback.answer("❌ Покупать бонусы может только глава клана.", show_alert=True)
        await clans_shop_handler(callback)
        return

                     
    cfg = {
        "hashrate10_24h": {"cost": 50_000.0, "percent": 0.10, "hours": 24},
        "hashrate25_24h": {"cost": 110_000.0, "percent": 0.25, "hours": 24},
        "hashrate10_72h": {"cost": 130_000.0, "percent": 0.10, "hours": 72},
        "hashrate25_72h": {"cost": 300_000.0, "percent": 0.25, "hours": 72},
    }

    item = cfg.get(str(bonus_key))
    if not item:
        await callback.answer("❌ Неизвестный бонус.", show_alert=True)
        return

    ok, msg = db.clan_buy_hashrate_bonus(
        owner_id,
        bonus_key=str(bonus_key),
        cost_usd=float(item["cost"]),
        percent=float(item["percent"]),
        duration_hours=int(item["hours"]),
    )
    await callback.answer(msg, show_alert=True)
    await clans_shop_handler(callback)


def _user_link(user_id: int, display_name: str) -> str:
    name = html.escape(display_name or str(user_id))
    return f"<a href=\"tg://user?id={int(user_id)}\">{name}</a>"


@router.message(Command("clan"))
async def clan_info_command(message: Message):
    user_id = int(message.from_user.id)
    save_chat_from_message(message)

    is_banned, ban_reason = check_user_banned(user_id)
    if is_banned:
        await message.answer(
            f"🚫 <b>Ваш аккаунт заблокирован!</b>\n\n"
            f"📋 <b>Причина:</b> {html.escape(ban_reason or '')}",
            parse_mode="HTML",
        )
        return

    clan = db.get_clan_for_user(user_id)

    if clan:
        clan_id = int(clan.get("clan_id") or 0)
        name = html.escape(str(clan.get("name") or ""))
        leader_id = int(clan.get("leader_id") or 0)
        role = html.escape(str(clan.get("member_role") or "member"))
        members = db.get_clan_member_count(clan_id)
        text = (
            "🏴 <b>Кланы</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏷 <b>Ваш клан:</b> {name}\n"
            f"🆔 <b>ID:</b> <code>{clan_id}</code>\n"
            f"👑 <b>Глава:</b> <code>{leader_id}</code>\n"
            f"👥 <b>Участников:</b> {members}\n"
            f"🎭 <b>Ваша роль:</b> {role}\n\n"
            "📨 <b>Приглашение:</b> ответьте на сообщение игрока и напишите\n"
            "<code>Отправить приглашение</code>\n"
            "или команду <code>/clan_invite</code>."
        )
    else:
        text = (
            "🏴 <b>Кланы</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🏳️ Вы пока не состоите в клане.\n\n"
            "Создать клан:\n"
            f"<code>/clan_create &lt;название&gt;</code>\n"
            f"Стоимость: <b>{CLAN_CREATE_COST_USD:,}</b> USD".replace(",", " ")
        )

    clans_file_id = (db.get_setting("ui_image_clans", "") or "").strip()
    await render_ui_from_message(
        message=message,
        owner_id=user_id,
        text=text,
        reply_markup=get_clans_keyboard(int(user_id), has_clan=bool(clan), is_leader=(str(clan.get("member_role")) == "leader") if clan else False),
        parse_mode="HTML",
        ui_key="clans",
        photo=(clans_file_id if clans_file_id else ""),
    )

    try:
        await message.delete()
    except Exception:
        pass


@router.message(Command("clan_create"))
@router.message(F.text.startswith("/clan_create"))
async def clan_create_command(message: Message):
    user_id = int(message.from_user.id)
    save_chat_from_message(message)

    is_banned, ban_reason = check_user_banned(user_id)
    if is_banned:
        await message.answer(
            f"🚫 <b>Ваш аккаунт заблокирован!</b>\n\n"
            f"📋 <b>Причина:</b> {html.escape(ban_reason or '')}",
            parse_mode="HTML",
        )
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "❌ Укажите название клана.\n\n"
            "Пример: <code>/clan_create Synapse</code>\n\n"
            f"Стоимость: <b>{CLAN_CREATE_COST_USD:,}</b> USD".replace(",", " "),
            parse_mode="HTML",
        )
        return

    clan_name = parts[1].strip()
    ok, msg, clan_id = db.create_clan(user_id, clan_name, CLAN_CREATE_COST_USD)
    if not ok:
        await message.answer(msg, parse_mode="HTML")
        return

    await message.answer(
        "✅ <b>Клан создан!</b>\n\n"
        f"🆔 ID: <code>{int(clan_id or 0)}</code>\n"
        f"🏷 Название: <b>{html.escape(clan_name)}</b>",
        parse_mode="HTML",
    )


@router.message(Command("clan_invite"))
@router.message(F.text.startswith("/clan_invite"))
@router.message(F.text.lower() == "отправить приглашение")
async def clan_invite_command(message: Message):
    inviter_id = int(message.from_user.id)
    save_chat_from_message(message)

    is_banned, ban_reason = check_user_banned(inviter_id)
    if is_banned:
        await message.answer(
            f"🚫 <b>Ваш аккаунт заблокирован!</b>\n\n"
            f"📋 <b>Причина:</b> {html.escape(ban_reason or '')}",
            parse_mode="HTML",
        )
        return

    reply = message.reply_to_message
    if reply is None or reply.from_user is None or reply.from_user.is_bot:
        await message.answer(
            "❌ Используйте эту команду <b>ответом</b> на сообщение игрока, которого хотите пригласить.",
            parse_mode="HTML",
        )
        return

    invitee_id = int(reply.from_user.id)

    is_invitee_banned, _ban_reason = check_user_banned(invitee_id)
    if is_invitee_banned:
        await message.answer("❌ Нельзя пригласить заблокированного игрока.")
        return

    try:
        if not db.get_user(invitee_id):
            db.create_user(invitee_id, getattr(reply.from_user, "username", None))
    except Exception:
        pass

    clan = db.get_clan_for_user(inviter_id)
    if not clan:
        await message.answer("❌ Вы не состоите в клане.")
        return

    clan_id = int(clan.get("clan_id") or 0)
    ok, msg, token = db.create_clan_invite(clan_id, inviter_id, invitee_id)
    if not ok:
        await message.answer(msg, parse_mode="HTML")
        return

    clan_name = html.escape(str(clan.get("name") or ""))
    inviter_name = getattr(message.from_user, "full_name", None) or str(inviter_id)
    invitee_name = getattr(reply.from_user, "full_name", None) or str(invitee_id)

    text = (
        "📨 <b>Приглашение в клан</b>\n\n"
        f"👑 От: {_user_link(inviter_id, inviter_name)}\n"
        f"🏷 Клан: <b>{clan_name}</b>\n\n"
        f"👉 Для: {_user_link(invitee_id, invitee_name)}\n\n"
        "Нажмите кнопку ниже, чтобы принять."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принять приглашение",
                    callback_data=f"{CLAN_INVITE_ACCEPT_PREFIX}{token}_{invitee_id}",
                )
            ]
        ]
    )

    await message.bot.send_message(
        chat_id=int(message.chat.id),
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML",
        reply_to_message_id=int(reply.message_id),
    )


@router.callback_query(F.data.startswith(CLAN_INVITE_ACCEPT_PREFIX))
async def clan_accept_invite_callback(callback: CallbackQuery):
    save_chat_from_callback(callback)

    data = callback.data or ""
    raw = data[len(CLAN_INVITE_ACCEPT_PREFIX):]
    try:
        token, owner_id_raw = raw.rsplit("_", maxsplit=1)
        owner_id = int(owner_id_raw)
    except Exception:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    is_owner, _user_id = check_message_owner(callback, owner_id)
    if not is_owner:
        try:
            await callback.answer("❌ Это приглашение не для вас.", show_alert=True)
        except Exception:
            pass
        return

    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        try:
            await callback.answer(
                f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}",
                show_alert=True,
            )
        except Exception:
            pass
        return

    ok, msg, clan_id = db.accept_clan_invite(token, owner_id)
    try:
        await callback.answer(msg, show_alert=True)
    except Exception:
        pass

    if not ok:
        return

    if callback.message is None or callback.message.chat is None:
        return

    try:
        await safe_edit_message_text(
            bot=callback.bot,
            chat_id=int(callback.message.chat.id),
            message_id=int(callback.message.message_id),
            text=(
                "✅ <b>Приглашение принято</b>\n\n"
                f"Вы вступили в клан. ID: <code>{int(clan_id or 0)}</code>"
            ),
            reply_markup=None,
            parse_mode="HTML",
        )
    except Exception:
        pass
