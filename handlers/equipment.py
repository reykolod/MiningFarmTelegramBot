from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from database import db
from keyboards import get_equipment_keyboard, get_equipment_item_keyboard, get_back_to_farm_keyboard
from models import SHOP_ITEMS
from game_logic import uninstall_item_from_farm
from utils import (
    check_message_owner,
    handle_unauthorized_access,
    check_user_banned,
    save_chat_from_callback,
    render_ui_from_callback,
    set_ui_key_for_message,
)

router = Router()


@router.callback_query(F.data.startswith("main_equipment_"))
async def main_equipment_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                         
    try:
        owner_id = int(callback.data.replace("main_equipment_", ""))
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
    
                                                        
    user = db.get_user(owner_id)
    if not user:
        await callback.answer("❌ Пользователь не найден. Используйте /mining для регистрации.", show_alert=True)
        return

    await callback.answer()

    if callback.message is None or callback.message.chat is None:
        return
    set_ui_key_for_message(
        int(callback.message.chat.id),
        int(owner_id),
        int(callback.message.message_id),
        "equipment",
    )

    eq_file_id = (db.get_setting("ui_image_equipment", "") or "").strip()
    
    installed_items = db.get_installed_items(owner_id)
    
    if not installed_items:
        text = (
            f"⚙️ <b>ОБОРУДОВАНИЕ</b>\n"
            f"{'━' * 25}\n\n"
            f"📭 <b>На ферме не установлено оборудование</b>\n\n"
            f"📦 Установите предметы из инвентаря,\n"
            f"чтобы начать майнинг.\n\n"
            f"💡 <i>Установленное оборудование\n"
            f"влияет на хешрейт и другие\n"
            f"параметры фермы.</i>"
        )
        if callback.message is None or callback.message.chat is None:
            return
        await render_ui_from_callback(
            callback=callback,
            owner_id=owner_id,
            text=text,
            reply_markup=get_back_to_farm_keyboard(owner_id),
            parse_mode="HTML",
            ui_key="equipment",
            photo=(eq_file_id if eq_file_id else ""),
        )
        return
    
    text = (
        f"⚙️ <b>ОБОРУДОВАНИЕ</b>\n"
        f"{'━' * 25}\n\n"
        f"🔧 <b>Установленное оборудование:</b>\n\n"
    )
    
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard_buttons = []
    for item in installed_items:
        item_data = SHOP_ITEMS.get(item['item_id'])
        item_name = item_data.name if item_data else item['item_name']
        quantity = item['quantity']
        text += f"• {item_name} x{quantity}\n"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{item_name} x{quantity}",
                callback_data=f"equipment_item_{item['item_id']}_{owner_id}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(
        text="🔙 Назад к ферме",
        callback_data=f"back_to_farm_{owner_id}"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    if callback.message is None or callback.message.chat is None:
        return
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML",
        ui_key="equipment",
        photo=(eq_file_id if eq_file_id else ""),
    )


@router.callback_query(F.data.startswith("equipment_item_"))
async def equipment_item_detail(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                                   
                                                 
                                                                   
    data = callback.data.replace("equipment_item_", "")
                                                                    
    last_underscore = data.rfind("_")
    if last_underscore == -1:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return
    
    item_id = data[:last_underscore]
    try:
        owner_id = int(data[last_underscore + 1:])
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
    
                              
    item_installed = None
    for item in installed_items:
        if item['item_id'] == item_id:
            item_installed = item
            break
    
    if not item_installed:
        await callback.answer("❌ Предмет не найден на ферме", show_alert=True)
        return
    
    item_data = SHOP_ITEMS.get(item_id)
    if not item_data:
        await callback.answer("❌ Данные предмета не найдены", show_alert=True)
        return
    
    quantity = item_installed['quantity']
    
                                 
    effects_text = []
    if item_data.effects.get('hashrate', 0) > 0:
        effects_text.append(f"⚡ Хешрейт: +{item_data.effects['hashrate'] * quantity} H/s")
    if item_data.effects.get('power_consumption', 0) > 0:
        effects_text.append(f"🔌 Потребление: +{item_data.effects['power_consumption'] * quantity}W")
    if item_data.effects.get('heat', 0) > 0:
        effects_text.append(f"🌡️ Тепло: +{item_data.effects['heat'] * quantity}°C")
    if item_data.effects.get('psu_power', 0) > 0:
        effects_text.append(f"⚡ Мощность БП: +{item_data.effects['psu_power'] * quantity}W")
    if item_data.effects.get('cooling', 0) != 0:
        cooling = item_data.effects['cooling'] * quantity
        effects_text.append(f"❄️ Охлаждение: {cooling}°C")
    
    effects_str = "\n".join(effects_text) if effects_text else "Нет эффектов"
    
    text = (
        f"⚙️ <b>{item_data.name}</b>\n"
        f"{'━' * 25}\n\n"
        f"📝 <b>Описание:</b>\n{item_data.description}\n\n"
        f"📊 <b>Текущие характеристики:</b>\n{effects_str}\n\n"
        f"{'━' * 25}\n"
        f"📦 <b>Количество установлено:</b> {quantity} шт.\n\n"
        f"💡 <i>Снимите предмет с фермы,\n"
        f"чтобы вернуть его в инвентарь.</i>"
    )
    
    await callback.answer()
    if callback.message is None or callback.message.chat is None:
        return

    eq_file_id = (db.get_setting("ui_image_equipment", "") or "").strip()
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=text,
        reply_markup=get_equipment_item_keyboard(item_id, quantity, owner_id),
        parse_mode="HTML",
        ui_key="equipment",
        photo=(eq_file_id if eq_file_id else ""),
    )


@router.callback_query(F.data.startswith("uninstall_item_"))
async def uninstall_item_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                                   
                                                 
                                                                   
    data = callback.data.replace("uninstall_item_", "")
                                                                    
    last_underscore = data.rfind("_")
    if last_underscore == -1:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return
    
    item_id = data[:last_underscore]
    try:
        owner_id = int(data[last_underscore + 1:])
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
    
    success, message_text = uninstall_item_from_farm(owner_id, item_id, 1)
    
    if success:
        await callback.answer(message_text, show_alert=True)
                                     
        await main_equipment_handler(callback)
    else:
        await callback.answer(message_text, show_alert=True)

