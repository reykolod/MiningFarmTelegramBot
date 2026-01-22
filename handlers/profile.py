from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from database import db
from keyboards import get_back_to_farm_keyboard
from utils import (
    check_user_banned,
    save_chat_from_message,
    save_chat_from_callback,
    check_message_owner,
    handle_unauthorized_access,
    render_ui_from_message,
    render_ui_from_callback,
    set_ui_key_for_message,
)
import html

router = Router()


def format_profile_text(target_user: dict) -> str:
    user_id = target_user["user_id"]
    username_raw = target_user.get("username")
    username = html.escape(username_raw) if username_raw else f"ID: {user_id}"

                                    
    x2_mode = db.is_x2_mode_enabled()
    x2_weekend = db.is_x2_weekend_mode_enabled()
    x2_newyear = db.is_x2_newyear_mode_enabled()
    global_multiplier = float(db.get_current_hashrate_multiplier() or 1.0)

    clan_multiplier = float(db.get_clan_hashrate_bonus_multiplier(int(user_id)) or 1.0)
    total_multiplier = float(db.get_hashrate_multiplier_for_user(int(user_id)) or 1.0)

    x2_lines: list[str] = []
    if x2_mode:
        x2_lines.append("🔥 X2 (постоянный)")
    if x2_newyear:
        x2_lines.append("🎄 X2 (новогодний)")
    if x2_weekend:
        from datetime import datetime

        weekday = datetime.now().weekday()
        if weekday in (5, 6):
            x2_lines.append("🔥 X2 (выходные — активен)")
        else:
            x2_lines.append("⏰ X2 (выходные — ожидание)")
    if not x2_lines:
        x2_lines.append("❌ Выключен")

    bonus_lines: list[str] = []
    for line in x2_lines:
        if line != "❌ Выключен":
            bonus_lines.append(line)

    if clan_multiplier > 1.000001:
        bonus_lines.append(f"🏴 Клановый бонус: +{(clan_multiplier - 1.0) * 100:.0f}%")

    if not bonus_lines:
        bonus_lines.append("❌ Нет активных бонусов")

    bonuses_text = "\n".join(f"• {line}" for line in bonus_lines)

                        
    balance = target_user.get("balance", 0) or 0
    bitcoin_balance = target_user.get("bitcoin_balance", 0) or 0

                                 
    bank_balance = target_user.get("bank_balance", 0) or 0
    bank_bitcoin_balance = target_user.get("bank_bitcoin_balance", 0) or 0

                           
    wallet_address, _ = db.ensure_user_wallet_addresses(user_id)

    profile_text = (
        "👤 <b>Профиль игрока</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 <b>Игрок:</b> {username}\n"
        f"🆔 <b>ID:</b> {user_id}\n"
        f"🏷 <b>Адрес кошелька:</b>\n<code>{wallet_address}</code>\n\n"
        "💰 <b>Балансы (на руках):</b>\n"
        f"• USD: {balance:.2f}\n"
        f"• BTC: {bitcoin_balance:.8f}\n\n"
        "🏦 <b>Банк (защищено):</b>\n"
        f"• USD в банке: {bank_balance:.2f}\n"
        f"• BTC в банке: {bank_bitcoin_balance:.8f}\n\n"
        "🎁 <b>Активные бонусы:</b>\n"
        f"{bonuses_text}\n"
        f"• Множитель (глобальный): x{global_multiplier:.2f}\n"
        f"• Множитель (клан): x{clan_multiplier:.2f}\n"
        f"• Множитель (итог): x{total_multiplier:.2f}\n\n"
        "🔗 <b>Переводы:</b>\n"
        "• <code>/send usd &lt;адрес&gt; &lt;сумма&gt;</code>\n"
        "• <code>/send btc &lt;адрес&gt; &lt;сумма&gt;</code>\n\n"
        "⚙️ <b>Быстрые команды:</b>\n"
        "• /wallet — кошелек и банк\n"
        "• /mining — панель фермы\n"
        "• /shop — магазин\n"
        "• /inventory — инвентарь\n"
        "• /leaders — топ игроков\n"
        "• /help — помощь\n"
    )
    return profile_text


@router.message(Command("profile"))
@router.message(F.text.startswith("/profile"))
async def profile_command(message: Message):
    requester_id = message.from_user.id
    save_chat_from_message(message)

                                                                                                         
    is_banned, ban_reason = check_user_banned(requester_id)
    if is_banned:
        await message.answer(
            f"🚫 <b>Ваш аккаунт заблокирован!</b>\n\n"
            f"📋 <b>Причина:</b> {ban_reason}\n\n"
            f"💬 Для разблокировки обратитесь к администратору.",
            parse_mode="HTML"
        )
        return

                                                                  
    target_user_id = requester_id
    if message.reply_to_message and message.reply_to_message.from_user and not message.reply_to_message.from_user.is_bot:
        target_user_id = message.reply_to_message.from_user.id

    target_user = db.get_user(target_user_id)
    if not target_user:
        if target_user_id == requester_id:
                                                      
            db.create_user(target_user_id, message.from_user.username)
            target_user = db.get_user(target_user_id)
        else:
            await message.answer(
                "❌ Этот игрок ещё не зарегистрирован в игре.\n\n"
                "Пусть он напишет /mining, чтобы создать ферму.",
                parse_mode="HTML",
            )
            return

                       
    profile_text = format_profile_text(target_user)

    if target_user_id != requester_id:
        await message.answer(profile_text, parse_mode="HTML")
        return

    photo_key = (db.get_setting("ui_image_profile", "") or "").strip()
    await render_ui_from_message(
        message=message,
        owner_id=requester_id,
        text=profile_text,
        reply_markup=get_back_to_farm_keyboard(requester_id),
        parse_mode="HTML",
        prefer_reply_in_groups=True,
        ui_key="profile",
        photo=(photo_key if photo_key else ""),
    )


@router.callback_query(F.data.startswith("main_profile_"))
async def main_profile_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
    try:
        owner_id = int(callback.data.replace("main_profile_", ""))
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

    user = db.get_user(owner_id)
    if not user:
        await callback.answer("❌ Пользователь не найден. Используйте /mining для регистрации.", show_alert=True)
        return

    text = format_profile_text(user)

    if callback.message is None or callback.message.chat is None:
        return
    set_ui_key_for_message(
        int(callback.message.chat.id),
        int(owner_id),
        int(callback.message.message_id),
        "profile",
    )

    photo_key = (db.get_setting("ui_image_profile", "") or "").strip()
    await callback.answer()
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=text,
        reply_markup=get_back_to_farm_keyboard(owner_id),
        parse_mode="HTML",
        ui_key="profile",
        photo=(photo_key if photo_key else ""),
    )

