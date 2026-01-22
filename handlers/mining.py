from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime
import time
from database import db
from keyboards import get_mining_farm_keyboard, get_main_menu_keyboard
from game_logic import get_mining_status_text, collect_bitcoin, get_pending_bitcoin
from exchange_rate import get_bitcoin_exchange_rate
from utils import (
    check_message_owner,
    handle_unauthorized_access,
    check_user_banned,
    render_ui_from_callback,
    render_ui_from_message,
    set_ui_key_for_message,
    save_chat_from_message,
    save_chat_from_callback,
)

router = Router()


_last_refresh_by_user: dict[int, float] = {}


def _with_just_mined_block(base_text: str, user_id: int) -> str:
    user = db.get_user(int(user_id)) or {}
    pending_btc = float(user.get("pending_bitcoin", 0) or 0)
    rate = float(get_bitcoin_exchange_rate() or 0)
    pending_usd = pending_btc * rate if pending_btc > 0 and rate > 0 else 0.0
    time_str = datetime.now().strftime("%d.%m в %H:%M")

    lines: list[str] = [base_text.rstrip(), "", "─" * 16, "💰 <b>Добыто только что:</b>"]
    lines.append(f"• {pending_btc:.8f} BTC (≈{pending_usd:.2f} USD)")
    lines.append(time_str)
    return "\n".join(lines).strip()


@router.message(Command("mining"))
@router.message(F.text.startswith("/mining"))
async def cmd_mining(message: Message):
    user_id = message.from_user.id
    save_chat_from_message(message)
    
                          
    is_banned, ban_reason = check_user_banned(user_id)
    if is_banned:
        await message.answer(
            f"🚫 <b>Ваш аккаунт заблокирован!</b>\n\n"
            f"📋 <b>Причина блокировки:</b> {ban_reason}\n\n"
            f"💬 Для разблокировки обратитесь к администратору.",
            parse_mode="HTML"
        )
        return
    
    user = db.get_user(user_id)
    if not user:
                                                       
        db.create_user(user_id, message.from_user.username)
        user = db.get_user(user_id)
    
    status_text = get_mining_status_text(user_id)
    mining_enabled = db.is_mining_enabled(user_id)
    
                                                                                        
    keyboard = get_mining_farm_keyboard(user_id, mining_enabled)

    farm_file_id = (
        (db.get_setting("ui_image_mining", "") or "").strip()
        or (db.get_setting("ui_image_farm", "") or "").strip()
    )

    await render_ui_from_message(
        message=message,
        owner_id=user_id,
        text=status_text,
        reply_markup=keyboard,
        parse_mode="HTML",
        prefer_reply_in_groups=True,
        ui_key="mining",
        photo=(farm_file_id if farm_file_id else ""),
    )


@router.callback_query(F.data.startswith("back_to_farm_"))
async def back_to_farm(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                                
    try:
        owner_id = int(callback.data.replace("back_to_farm_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return
    
    is_owner, user_id = check_message_owner(callback, owner_id)
    
    if not is_owner:
        await handle_unauthorized_access(callback)
        return
    
                          
    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await callback.answer(
            f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}",
            show_alert=True
        )
        return

    now_ts = time.monotonic()
    last_ts = _last_refresh_by_user.get(owner_id, 0.0)
    if now_ts - last_ts < 0.25:
        try:
            await callback.answer()
        except Exception:
            pass
        return
    _last_refresh_by_user[owner_id] = now_ts
    
    await callback.answer()

    if callback.message is None or callback.message.chat is None:
        return

    set_ui_key_for_message(
        int(callback.message.chat.id),
        int(owner_id),
        int(callback.message.message_id),
        "mining",
    )

    farm_file_id = (
        (db.get_setting("ui_image_mining", "") or "").strip()
        or (db.get_setting("ui_image_farm", "") or "").strip()
    )
    status_text = get_mining_status_text(owner_id)
    mining_enabled = db.is_mining_enabled(owner_id)
    
                                             
    keyboard = get_mining_farm_keyboard(owner_id, mining_enabled)

    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=status_text,
        reply_markup=keyboard,
        parse_mode="HTML",
        ui_key="mining",
        photo=(farm_file_id if farm_file_id else ""),
    )


@router.callback_query(F.data.startswith("main_menu_"))
async def main_menu_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
    try:
        owner_id = int(callback.data.replace("main_menu_", ""))
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
        "☰ <b>МЕНЮ</b>\n"
        f"{'━' * 25}\n\n"
        "Выберите раздел:"
    )

    await callback.answer()

    if callback.message is None or callback.message.chat is None:
        return

    set_ui_key_for_message(
        int(callback.message.chat.id),
        int(owner_id),
        int(callback.message.message_id),
        "menu",
    )

    menu_file_id = (db.get_setting("ui_image_menu", "") or "").strip()
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=text,
        reply_markup=get_main_menu_keyboard(owner_id),
        parse_mode="HTML",
        ui_key="menu",
        photo=(menu_file_id if menu_file_id else ""),
    )


@router.callback_query(F.data.startswith("toggle_mining_"))
async def toggle_mining_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                                
    try:
        owner_id = int(callback.data.replace("toggle_mining_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return
    
    is_owner, user_id = check_message_owner(callback, owner_id)
    
    if not is_owner:
        await handle_unauthorized_access(callback)
        return
    
                          
    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await callback.answer(
            f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}",
            show_alert=True
        )
        return
    
                                                                    
    installed_items = db.get_installed_items(owner_id)
    current_state = db.is_mining_enabled(owner_id)
    
                                                                    
    if not current_state:
        from game_logic import calculate_user_stats
        from models import SHOP_ITEMS

        has_hashrate_equipment = False
        for it in installed_items:
            item_data = SHOP_ITEMS.get(it.get("item_id"))
            if not item_data:
                continue
            qty = int(it.get("quantity", 0) or 0)
            if qty <= 0:
                continue
            if float(item_data.effects.get("hashrate", 0) or 0) > 0:
                has_hashrate_equipment = True
                break

        stats = calculate_user_stats(owner_id)
        if not has_hashrate_equipment:
            await callback.answer(
                "❌ Невозможно включить майнинг!\n\n"
                "Установите оборудование с хешрейтом (GPU, ASIC или майнинг-риги).",
                show_alert=True
            )
            return

        power_consumption = float(stats.get("power_consumption", 0) or 0)
        psu_power = float(stats.get("psu_power", 0) or 0)
        if power_consumption > 0 and (psu_power <= 0 or power_consumption > psu_power):
            await callback.answer(
                "❌ Невозможно включить майнинг!\n\n"
                f"Недостаточно мощности БП: {power_consumption:.0f}W / {psu_power:.0f}W",
                show_alert=True,
            )
            return

        from game_logic import validate_rig_configuration

        rig_ok, rig_error = validate_rig_configuration(owner_id)
        if not rig_ok:
            await callback.answer(rig_error or "❌ Невозможно включить майнинг.", show_alert=True)
            return

                                                   
        from database import db as _db
        from game_logic import calculate_effective_temperature, TEMP_CRITICAL_C

        dust_level, _ = _db.get_dust_state(owner_id)
        effective_temp = calculate_effective_temperature(stats, dust_level)
        if effective_temp >= TEMP_CRITICAL_C:
            await callback.answer(
                "❌ Невозможно включить майнинг!\n\n"
                f"Критический перегрев: {effective_temp:.1f}°C",
                show_alert=True,
            )
            return
    
                                    
    if current_state:
        from game_logic import calculate_user_stats, get_pending_bitcoin

        now_dt = datetime.now()
        stats_snapshot = calculate_user_stats(owner_id)
        stats_snapshot["pending_bitcoin"] = get_pending_bitcoin(owner_id, update_db=False)
        stats_snapshot["last_collect_time"] = now_dt
        db.update_user_stats(owner_id, stats_snapshot)

    new_state = db.toggle_mining(owner_id)

    if new_state:
        from game_logic import calculate_user_stats

        now_dt = datetime.now()
        user = db.get_user(owner_id) or {}
        stats_snapshot = calculate_user_stats(owner_id)
        stats_snapshot["pending_bitcoin"] = float(user.get("pending_bitcoin", 0) or 0)
        stats_snapshot["last_collect_time"] = now_dt
        db.update_user_stats(owner_id, stats_snapshot)
    
    if new_state:
        await callback.answer("✅ Майнинг-ферма включена!", show_alert=True)
    else:
        await callback.answer("⏸️ Майнинг-ферма выключена!", show_alert=True)
    
                                          
    status_text = get_mining_status_text(owner_id)
    mining_enabled = db.is_mining_enabled(owner_id)
    
                                             
    keyboard = get_mining_farm_keyboard(owner_id, mining_enabled)

    farm_file_id = (
        (db.get_setting("ui_image_mining", "") or "").strip()
        or (db.get_setting("ui_image_farm", "") or "").strip()
    )
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=status_text,
        reply_markup=keyboard,
        parse_mode="HTML",
        ui_key="mining",
        photo=None,
    )


@router.callback_query(F.data.startswith("refresh_mining_"))
async def refresh_mining(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                                
    try:
        owner_id = int(callback.data.replace("refresh_mining_", ""))
    except ValueError:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return
    
    is_owner, user_id = check_message_owner(callback, owner_id)
    
    if not is_owner:
        await handle_unauthorized_access(callback)
        return
    
                          
    is_banned, ban_reason = check_user_banned(owner_id)
    if is_banned:
        await callback.answer(
            f"🚫 Ваш аккаунт заблокирован!\n\nПричина: {ban_reason}",
            show_alert=True
        )
        return
    
    await callback.answer("🔄 Обновлено")

    if callback.message is None or callback.message.chat is None:
        return

    set_ui_key_for_message(
        int(callback.message.chat.id),
        int(owner_id),
        int(callback.message.message_id),
        "mining",
    )

    try:
        get_pending_bitcoin(int(owner_id), update_db=True)
    except Exception:
        pass

                                                                
    status_text = _with_just_mined_block(get_mining_status_text(owner_id), owner_id)
    mining_enabled = db.is_mining_enabled(owner_id)
    
                                             
    keyboard = get_mining_farm_keyboard(owner_id, mining_enabled)

    if callback.message is None or callback.message.chat is None:
        return

    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=status_text,
        reply_markup=keyboard,
        parse_mode="HTML",
        ui_key="mining",
        photo=None,
    )
