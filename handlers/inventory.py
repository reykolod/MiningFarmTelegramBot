import math

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from database import db
from keyboards import get_inventory_keyboard, get_inventory_item_keyboard, get_back_to_farm_keyboard
from models import SHOP_ITEMS, get_item_price_usd
from game_logic import install_item_from_inventory
from utils import (
    check_message_owner,
    handle_unauthorized_access,
    check_user_banned,
    render_ui_from_callback,
    render_ui_from_message,
    save_chat_from_message,
    save_chat_from_callback,
    set_ui_key_for_message,
)

router = Router()


@router.message(Command("inv"))
@router.message(Command("inventory"))
@router.message(F.text.startswith("/inv"))
@router.message(F.text.startswith("/inventory"))
async def cmd_inventory(message: Message):
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
        await message.answer("❌ Вы ещё не зарегистрированы. Используйте /mining для начала игры.")
        return
    
    inventory = db.get_user_inventory(user_id)

    inv_file_id = (db.get_setting("ui_image_inventory", "") or "").strip()
    desired_photo = (inv_file_id if inv_file_id else "")
    
    if not inventory:
        text = (
            f"📦 <b>ИНВЕНТАРЬ</b>\n"
            f"{'━' * 25}\n\n"
            f"📭 <b>Ваш инвентарь пуст</b>\n\n"
            f"🛒 Купите предметы в магазине,\n"
            f"чтобы они появились здесь.\n\n"
            f"💡 <i>Купленные предметы попадают\n"
            f"в инвентарь и могут быть\n"
            f"установлены на ферму.</i>"
        )
        await render_ui_from_message(
            message=message,
            owner_id=user_id,
            text=text,
            reply_markup=get_back_to_farm_keyboard(user_id),
            parse_mode="HTML",
            prefer_reply_in_groups=True,
            ui_key="inventory",
            photo=desired_photo,
        )
        return
    
    text = (
        f"📦 <b>ИНВЕНТАРЬ</b>\n"
        f"{'━' * 25}\n\n"
        f"📋 <b>Купленные предметы:</b>\n\n"
    )
    
    keyboard_buttons = []
    for item in inventory:
        item_data = SHOP_ITEMS.get(item['item_id'])
        item_name = item_data.name if item_data else item['item_name']
        quantity = item['quantity']
        text += f"• {item_name} x{quantity}\n"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{item_name} x{quantity}",
                callback_data=f"inventory_item_{item['item_id']}_{user_id}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(
        text="🔙 Назад к ферме",
        callback_data=f"back_to_farm_{user_id}"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await render_ui_from_message(
        message=message,
        owner_id=user_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML",
        prefer_reply_in_groups=True,
        ui_key="inventory",
        photo=desired_photo,
    )


@router.callback_query(F.data.startswith("main_inventory_"))
async def main_inventory_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                         
    try:
        owner_id = int(callback.data.replace("main_inventory_", ""))
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

    if callback.message is None or callback.message.chat is None:
        return
    set_ui_key_for_message(
        int(callback.message.chat.id),
        int(owner_id),
        int(callback.message.message_id),
        "inventory",
    )

    inv_file_id = (db.get_setting("ui_image_inventory", "") or "").strip()
    
    inventory = db.get_user_inventory(owner_id)
    
    if not inventory:
        text = (
            f"📦 <b>ИНВЕНТАРЬ</b>\n"
            f"{'━' * 25}\n\n"
            f"📭 <b>Ваш инвентарь пуст</b>\n\n"
            f"🛒 Купите предметы в магазине,\n"
            f"чтобы они появились здесь.\n\n"
            f"💡 <i>Купленные предметы попадают\n"
            f"в инвентарь и могут быть\n"
            f"установлены на ферму.</i>"
        )
        await callback.answer()
        if callback.message is None or callback.message.chat is None:
            return
        await render_ui_from_callback(
            callback=callback,
            owner_id=owner_id,
            text=text,
            reply_markup=get_back_to_farm_keyboard(owner_id),
            parse_mode="HTML",
            ui_key="inventory",
            photo=(inv_file_id if inv_file_id else ""),
        )
        return
    
    text = (
        f"📦 <b>ИНВЕНТАРЬ</b>\n"
        f"{'━' * 25}\n\n"
        f"📋 <b>Купленные предметы:</b>\n\n"
    )
    
    keyboard_buttons = []
    for item in inventory:
        item_data = SHOP_ITEMS.get(item['item_id'])
        item_name = item_data.name if item_data else item['item_name']
        quantity = item['quantity']
        text += f"• {item_name} x{quantity}\n"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{item_name} x{quantity}",
                callback_data=f"inventory_item_{item['item_id']}_{owner_id}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(
        text="🔙 Назад к ферме",
        callback_data=f"back_to_farm_{owner_id}"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.answer()
    if callback.message is None or callback.message.chat is None:
        return
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML",
        ui_key="inventory",
        photo=(inv_file_id if inv_file_id else ""),
    )


@router.callback_query(F.data.startswith("inventory_item_"))
async def inventory_item_detail(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                                   
                                                 
                                                                   
    data = callback.data.replace("inventory_item_", "")
                                                                    
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
    
    inventory = db.get_user_inventory(owner_id)
    
                                 
    item_in_inventory = None
    for item in inventory:
        if item['item_id'] == item_id:
            item_in_inventory = item
            break
    
    if not item_in_inventory:
        await callback.answer("❌ Предмет не найден в инвентаре", show_alert=True)
        return
    
    item_data = SHOP_ITEMS.get(item_id)
    if not item_data:
        await callback.answer("❌ Данные предмета не найдены", show_alert=True)
        return
    
    quantity = item_in_inventory['quantity']
    
                                 
    effects_text = []
    if item_data.effects.get('hashrate', 0) > 0:
        effects_text.append(f"⚡ Хешрейт: +{item_data.effects['hashrate']} H/s")
    if item_data.effects.get('power_consumption', 0) > 0:
        effects_text.append(f"🔌 Потребление: +{item_data.effects['power_consumption']}W")
    if item_data.effects.get('heat', 0) > 0:
        effects_text.append(f"🌡️ Тепло: +{item_data.effects['heat']}°C")
    if item_data.effects.get('psu_power', 0) > 0:
        effects_text.append(f"⚡ Мощность БП: +{item_data.effects['psu_power']}W")
    if item_data.effects.get('cooling', 0) != 0:
        cooling = item_data.effects['cooling']
        effects_text.append(f"❄️ Охлаждение: {cooling}°C")
    
    effects_str = "\n".join(effects_text) if effects_text else "Нет эффектов"

    hint_text = "💡 <i>Установите предмет на ферму,\nчтобы получить эффекты.</i>"
    if item_data.item_type == "consumable":
        hint_text = "💡 <i>Используйте расходник в инвентаре,\nчтобы применить эффект.</i>"
    
    text = (
        f"📦 <b>{item_data.name}</b>\n"
        f"{'━' * 25}\n\n"
        f"📝 <b>Описание:</b>\n{item_data.description}\n\n"
        f"📊 <b>Характеристики:</b>\n{effects_str}\n\n"
        f"{'━' * 25}\n"
        f"📦 <b>Количество в инвентаре:</b> {quantity} шт.\n\n"
        f"{hint_text}"
    )
    
    await callback.answer()
    if callback.message is None or callback.message.chat is None:
        return

    inv_file_id = (db.get_setting("ui_image_inventory", "") or "").strip()
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=text,
        reply_markup=get_inventory_item_keyboard(item_id, quantity, owner_id),
        parse_mode="HTML",
        ui_key="inventory",
        photo=(inv_file_id if inv_file_id else ""),
    )


@router.callback_query(F.data.startswith("install_item_"))
async def install_item_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                                   
                                               
                                                                   
    data = callback.data.replace("install_item_", "")
                                                                    
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
    
    success, message_text = install_item_from_inventory(owner_id, item_id, 1)
    
    if success:
        await callback.answer(message_text, show_alert=True)
                                  
        await main_inventory_handler(callback)
    else:
        await callback.answer(message_text, show_alert=True)


@router.callback_query(F.data.startswith("repair_item_"))
async def repair_item_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
    data = callback.data.replace("repair_item_", "")
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
    
    from game_logic import repair_equipment_from_inventory
    success, message_text, cost = repair_equipment_from_inventory(owner_id, item_id, 1)
    
    if success:
        await callback.answer(message_text, show_alert=True)
                                                                             
        inventory = db.get_user_inventory(owner_id)
        item_in_inventory = None
        for item in inventory:
            if item['item_id'] == item_id:
                item_in_inventory = item
                break
        
        if item_in_inventory:
            item_data = SHOP_ITEMS.get(item_id)
            if item_data:
                quantity = item_in_inventory['quantity']
                
                effects_text = []
                if item_data.effects.get('hashrate', 0) > 0:
                    effects_text.append(f"⚡ Хешрейт: +{item_data.effects['hashrate']} H/s")
                if item_data.effects.get('power_consumption', 0) > 0:
                    effects_text.append(f"🔌 Потребление: +{item_data.effects['power_consumption']}W")
                if item_data.effects.get('heat', 0) > 0:
                    effects_text.append(f"🌡️ Тепло: +{item_data.effects['heat']}°C")
                if item_data.effects.get('psu_power', 0) > 0:
                    effects_text.append(f"⚡ Мощность БП: +{item_data.effects['psu_power']}W")
                if item_data.effects.get('cooling', 0) != 0:
                    cooling = item_data.effects['cooling']
                    effects_text.append(f"❄️ Охлаждение: {cooling}°C")
                
                effects_str = "\n".join(effects_text) if effects_text else "Нет эффектов"

                hint_text = "💡 <i>Установите предмет на ферму,\nчтобы получить эффекты.</i>"
                if item_data.item_type == "consumable":
                    hint_text = "💡 <i>Используйте расходник в инвентаре,\nчтобы применить эффект.</i>"
                
                text = (
                    f"📦 <b>{item_data.name}</b>\n"
                    f"{'━' * 25}\n\n"
                    f"📝 <b>Описание:</b>\n{item_data.description}\n\n"
                    f"📊 <b>Характеристики:</b>\n{effects_str}\n\n"
                    f"{'━' * 25}\n"
                    f"📦 <b>Количество в инвентаре:</b> {quantity} шт.\n\n"
                    f"{hint_text}"
                )
                
                if callback.message is None or callback.message.chat is None:
                    return

                inv_file_id = (db.get_setting("ui_image_inventory", "") or "").strip()
                await render_ui_from_callback(
                    callback=callback,
                    owner_id=owner_id,
                    text=text,
                    reply_markup=get_inventory_item_keyboard(item_id, quantity, owner_id),
                    parse_mode="HTML",
                    ui_key="inventory",
                    photo=(inv_file_id if inv_file_id else ""),
                )
    else:
        await callback.answer(message_text, show_alert=True)


@router.callback_query(F.data.startswith("use_consumable_"))
async def use_consumable_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
    data = callback.data.replace("use_consumable_", "")
    last_underscore = data.rfind("_")
    if last_underscore == -1:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    item_id = data[:last_underscore]
    try:
        owner_id = int(data[last_underscore + 1 :])
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
            show_alert=True,
        )
        return

                                                              
    item_data = SHOP_ITEMS.get(item_id)
    if not item_data or item_data.item_type != "consumable":
        await callback.answer("❌ Этот предмет нельзя использовать как расходник.", show_alert=True)
        return

                                   
    inventory = db.get_user_inventory(owner_id)
    item_in_inventory = None
    for it in inventory:
        if it["item_id"] == item_id and it["quantity"] > 0:
            item_in_inventory = it
            break

    if not item_in_inventory:
        await callback.answer("❌ В инвентаре нет такого расходника.", show_alert=True)
        return

                                       
    if item_id == "consumable_air":
                      
        db.update_dust_state(owner_id, 0.0)
        effect_text = "🧹 Вся пыль с вашей фермы успешно удалена! Температура стала ниже."
    else:
        effect_text = "✅ Расходник использован."

                                           
    db.cursor.execute(
        """
        UPDATE inventory
        SET quantity = quantity - 1
        WHERE user_id = ? AND item_id = ? AND quantity > 0
        """,
        (owner_id, item_id),
    )
    db.cursor.execute(
        "DELETE FROM inventory WHERE user_id = ? AND item_id = ? AND quantity <= 0",
        (owner_id, item_id),
    )
    db.conn.commit()

    await callback.answer(effect_text, show_alert=True)
                                             
    await main_inventory_handler(callback)


@router.callback_query(F.data.startswith("scrap_item_"))
async def scrap_item_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
    data = callback.data.replace("scrap_item_", "")
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
    
    from game_logic import scrap_equipment_from_inventory
    success, message_text, value = scrap_equipment_from_inventory(owner_id, item_id, 1)
    
    if success:
        await callback.answer(message_text, show_alert=True)
                                  
        await main_inventory_handler(callback)
    else:
        await callback.answer(message_text, show_alert=True)


@router.callback_query(F.data.startswith("fence_offer_"))
async def fence_offer_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
    data = callback.data.replace("fence_offer_", "")
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
            show_alert=True,
        )
        return

                                            
    inventory = db.get_user_inventory(owner_id)
    item_in_inventory = None
    for it in inventory:
        if it["item_id"] == item_id:
            item_in_inventory = it
            break

    if not item_in_inventory:
        await callback.answer("❌ В инвентаре нет предмета для продажи.", show_alert=True)
        return

    quantity = item_in_inventory["quantity"]
    if quantity <= 0:
        await callback.answer("❌ В инвентаре нет предметов для продажи.", show_alert=True)
        return

    item_data = SHOP_ITEMS.get(item_id)
    if not item_data:
        await callback.answer("❌ Невозможно определить цену этого предмета.", show_alert=True)
        return
    
                                                      
    buy_price = float(get_item_price_usd(item_id) or 0)
    base_sell_percent = 0.70
    sell_price_per_item = int((math.ceil((buy_price * base_sell_percent) / 50.0) * 50.0))
    total_value = int(sell_price_per_item * quantity)
    
    text = (
        f"🕵️ <b>БАРЫГА</b>\n"
        f"{'━' * 25}\n\n"
        f"😏 <i>\"Неплохой товар! Возьму за хорошую цену.\"</i>\n\n"
        f"📦 <b>Товар:</b> {item_data.name}\n"
        f"🔢 <b>Количество:</b> {quantity} шт.\n\n"
        f"{'━' * 25}\n"
        f"💰 <b>Моя цена:</b> <code>{total_value:.0f} USD</code>\n"
        f"<i>(70% от магазинной цены)</i>\n\n"
        f"🤝 <i>Ну что, по рукам?</i>"
    )
    
    from keyboards import get_fence_offer_keyboard
    await callback.answer()
    if callback.message is None or callback.message.chat is None:
        return

    inv_file_id = (db.get_setting("ui_image_inventory", "") or "").strip()
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=text,
        reply_markup=get_fence_offer_keyboard(item_id, owner_id),
        parse_mode="HTML",
        ui_key="inventory",
        photo=(inv_file_id if inv_file_id else ""),
    )


@router.callback_query(F.data.startswith("sell_confirm_"))
async def sell_confirm_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
    data = callback.data.replace("sell_confirm_", "")
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
            show_alert=True,
        )
        return

                                            
    inventory = db.get_user_inventory(owner_id)
    item_in_inventory = None
    for it in inventory:
        if it["item_id"] == item_id:
            item_in_inventory = it
            break

    if not item_in_inventory:
        await callback.answer("❌ В инвентаре нет предмета для продажи.", show_alert=True)
        return

    quantity = item_in_inventory["quantity"]
    if quantity <= 0:
        await callback.answer("❌ В инвентаре нет предметов для продажи.", show_alert=True)
        return

    item_data = SHOP_ITEMS.get(item_id)
    if not item_data:
        await callback.answer("❌ Невозможно определить цену этого предмета.", show_alert=True)
        return
    
                                                      
    buy_price = float(get_item_price_usd(item_id) or 0)
    base_sell_percent = 0.70
    sell_price_per_item = int((math.ceil((buy_price * base_sell_percent) / 50.0) * 50.0))
    total_value = int(sell_price_per_item * quantity)

                                            
    db.cursor.execute(
        "DELETE FROM inventory WHERE user_id = ? AND item_id = ?",
        (owner_id, item_id),
    )
    db.conn.commit()

                                                                           
    db.update_user_balance(owner_id, total_value)

    await callback.answer(
        f"💸 Сделка совершена!\nВы получили {total_value:.0f} USD за {quantity} шт.",
        show_alert=True,
    )
                         
    await main_inventory_handler(callback)

