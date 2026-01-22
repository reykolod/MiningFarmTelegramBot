import math

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from database import db
from exchange_rate import get_bitcoin_exchange_rate
from game_logic import (
    calculate_user_stats,
    get_pending_bitcoin,
    validate_rig_configuration,
    calculate_effective_temperature,
    heat_penalty_factor,
    MINING_HASHRATE_EXPONENT,
    BTC_PER_HOUR_PER_HASHRATE_UNIT,
    TEMP_CRITICAL_C,
)
from keyboards import get_back_to_farm_keyboard
from utils import (
    check_user_banned,
    check_message_owner,
    handle_unauthorized_access,
    render_ui_from_message,
    render_ui_from_callback,
    save_chat_from_message,
    save_chat_from_callback,
    set_ui_key_for_message,
    get_ui_key_for_message,
)


router = Router()


def _format_hs(value_hs: float) -> str:
    v = float(value_hs or 0)
    if v >= 1_000_000_000_000:
        return f"{v / 1_000_000_000_000:.3f} TH/s"
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.3f} GH/s"
    return f"{v:.2f} H/s"


def _format_income_table(btc_per_hour: float, rate_usd_per_btc: float) -> str:
    btc_per_second = float(btc_per_hour or 0) / 3600.0
    has_rate = float(rate_usd_per_btc or 0) > 0

    rows: list[tuple[str, float]] = [
        ("1 сек", 1.0),
        ("10 сек", 10.0),
        ("1 мин", 60.0),
        ("10 мин", 600.0),
        ("1 час", 3600.0),
        ("1 день", 86400.0),
        ("1 неделя", 7.0 * 86400.0),
        ("1 месяц", 30.0 * 86400.0),
    ]

    lines: list[str] = []
    lines.append("⏱ <b>Таблица дохода</b>")
    if btc_per_hour <= 0:
        lines.append("• Сейчас доход = 0 (ферма не может майнить).")
        return "\n".join(lines)

    for label, seconds in rows:
        btc_amount = btc_per_second * float(seconds)
        if has_rate:
            usd_amount = btc_amount * float(rate_usd_per_btc)
            lines.append(f"• {label:<8} | {btc_amount:.8f} BTC | ≈ {usd_amount:.2f} USD")
        else:
            lines.append(f"• {label:<8} | {btc_amount:.8f} BTC")

    return "\n".join(lines)


def _build_info_text(user_id: int) -> str:
    user = db.get_user(user_id)
    if not user:
        return "❌ Пользователь не найден. Используйте /mining для регистрации."

    try:
                                                                                          
        get_pending_bitcoin(user_id, update_db=True)
        user = db.get_user(user_id) or user
    except Exception:
        pass

    stats = calculate_user_stats(user_id)

    mining_enabled = (user.get("mining_enabled", 0) or 0) == 1

    dust_level, _ = db.get_dust_state(user_id)
    rig_ok, rig_error = validate_rig_configuration(user_id)

    power_consumption = float(stats.get("power_consumption", 0) or 0)
    psu_power = float(stats.get("psu_power", 0) or 0)
    power_ok = True
    if power_consumption > 0 and (psu_power <= 0 or power_consumption > psu_power):
        power_ok = False

    effective_temp = calculate_effective_temperature(stats, dust_level)
    heat_penalty = heat_penalty_factor(effective_temp)

    hashrate_raw = float(stats.get("hashrate", 0) or 0)
    hashrate_multiplier = float(db.get_hashrate_multiplier_for_user(user_id) or 1.0)

    can_mine = mining_enabled and power_ok and rig_ok and effective_temp < TEMP_CRITICAL_C
    hashrate_effective = hashrate_raw * (heat_penalty if can_mine else 0.0)
    hashrate_with_bonuses = hashrate_effective * hashrate_multiplier

    btc_per_hour = (
        math.pow(float(hashrate_with_bonuses), float(MINING_HASHRATE_EXPONENT))
        * float(BTC_PER_HOUR_PER_HASHRATE_UNIT)
        if hashrate_with_bonuses > 0
        else 0.0
    )
    rate = float(get_bitcoin_exchange_rate() or 0)

    text_lines: list[str] = []
    text_lines.append("ℹ️ <b>Информация о ферме</b>")
    text_lines.append("━━━━━━━━━━━━━━━━━━━━")
    text_lines.append("⚡ <b>Хешрейт</b>")
    text_lines.append(f"• Текущий: {_format_hs(hashrate_with_bonuses)}")
    text_lines.append("")
    text_lines.append(_format_income_table(btc_per_hour, rate))

    return "\n".join(text_lines)


@router.message(Command("info"))
@router.message(F.text.startswith("/info"))
async def cmd_info(message: Message):
    user_id = message.from_user.id
    save_chat_from_message(message)

    is_banned, ban_reason = check_user_banned(user_id)
    if is_banned:
        await message.answer(
            f"🚫 <b>Ваш аккаунт заблокирован!</b>\n\n"
            f"📋 <b>Причина блокировки:</b> {ban_reason}",
            parse_mode="HTML",
        )
        return

    text = _build_info_text(user_id)

    info_file_id = (db.get_setting("ui_image_info", "") or "").strip()
    await render_ui_from_message(
        message=message,
        owner_id=user_id,
        text=text,
        reply_markup=get_back_to_farm_keyboard(user_id),
        parse_mode="HTML",
        disable_web_page_preview=True,
        prefer_reply_in_groups=True,
        ui_key="info",
        photo=(info_file_id if info_file_id else ""),
    )


@router.callback_query(F.data.startswith("main_info_"))
async def main_info_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
    try:
        owner_id = int(callback.data.replace("main_info_", ""))
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

    text = _build_info_text(owner_id)

    await callback.answer()

    if callback.message is None or callback.message.chat is None:
        return

    chat_id = int(callback.message.chat.id)
    message_id = int(callback.message.message_id)
    current_key = (get_ui_key_for_message(chat_id, int(owner_id), message_id) or "").strip().lower()

    if current_key == "menu":
        target_key = "menu"
        photo_key = (db.get_setting("ui_image_menu", "") or "").strip()
    else:
        target_key = "info"
        photo_key = (db.get_setting("ui_image_info", "") or "").strip()

    set_ui_key_for_message(chat_id, int(owner_id), message_id, target_key)
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=text,
        reply_markup=get_back_to_farm_keyboard(owner_id),
        parse_mode="HTML",
        disable_web_page_preview=True,
        ui_key=target_key,
        photo=(photo_key if photo_key else ""),
    )
