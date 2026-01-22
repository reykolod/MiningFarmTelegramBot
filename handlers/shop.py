from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from typing import Optional
from database import db
from keyboards import (
    get_shop_categories_keyboard,
    get_category_items_keyboard,
    get_item_detail_keyboard,
    get_back_to_farm_keyboard,
)
from models import SHOP_ITEMS, SHOP_CATEGORIES, CATEGORY_NAMES, get_item_price_usd
from game_logic import buy_item
from utils import (
    check_message_owner,
    handle_unauthorized_access,
    check_user_banned,
    render_ui_from_callback,
    render_ui_from_message,
    save_chat_from_message,
    set_ui_key_for_message,
)

router = Router()


async def _edit(callback: CallbackQuery, owner_id: int, text: str, reply_markup, photo: Optional[str] = None) -> None:
    if photo is None:
        shop_file_id = (db.get_setting("ui_image_shop", "") or "").strip()
        photo = (shop_file_id if shop_file_id else "")
    await render_ui_from_callback(
        callback=callback,
        owner_id=int(owner_id),
        text=text,
        reply_markup=reply_markup,
        parse_mode="HTML",
        ui_key="shop",
        photo=photo,
    )


@router.message(Command("shop"))
@router.message(F.text.startswith("/shop"))
async def cmd_shop(message: Message):
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
    
    balance = user.get('balance', 0) or 0
    
    shop_text = (
        f"🛒 <b>МАГАЗИН ОБОРУДОВАНИЯ</b>\n"
        f"{'━' * 25}\n\n"
        f"💰 <b>Ваш баланс:</b> {balance:.2f} USD\n\n"
        f"📦 <b>Доступные категории:</b>\n\n"
        f"Выберите категорию для просмотра товаров:"
    )

    shop_file_id = (db.get_setting("ui_image_shop", "") or "").strip()
    await render_ui_from_message(
        message=message,
        owner_id=user_id,
        text=shop_text,
        reply_markup=get_shop_categories_keyboard(user_id),
        parse_mode="HTML",
        prefer_reply_in_groups=True,
        ui_key="shop",
        photo=(shop_file_id if shop_file_id else ""),
    )


@router.callback_query(F.data.startswith("main_shop_"))
async def main_shop_handler(callback: CallbackQuery):
                                         
    try:
        owner_id = int(callback.data.replace("main_shop_", ""))
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
    
    balance = user.get('balance', 0) or 0
    
    shop_text = (
        f"🛒 <b>МАГАЗИН ОБОРУДОВАНИЯ</b>\n"
        f"{'━' * 25}\n\n"
        f"💰 <b>Ваш баланс:</b> {balance:.2f} USD\n\n"
        f"📦 <b>Доступные категории:</b>\n\n"
        f"Выберите категорию для просмотра товаров:"
    )
    
    await callback.answer()

    if callback.message is None or callback.message.chat is None:
        return
    set_ui_key_for_message(
        int(callback.message.chat.id),
        int(owner_id),
        int(callback.message.message_id),
        "shop",
    )

    shop_file_id = (db.get_setting("ui_image_shop", "") or "").strip()
                                           
    await _edit(
        callback,
        owner_id,
        shop_text,
        get_shop_categories_keyboard(owner_id),
        photo=(shop_file_id if shop_file_id else ""),
    )


@router.callback_query(F.data.startswith("shop_category_"))
async def show_category(callback: CallbackQuery):
    data = callback.data.replace("shop_category_", "")
                                                                     
    last_underscore = data.rfind("_")
    if last_underscore == -1:
                                                        
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return
    
    category = data[:last_underscore]
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
    
    if category not in SHOP_CATEGORIES:
        await callback.answer("❌ Категория не найдена", show_alert=True)
        return
    
    user = db.get_user(owner_id)
    balance = user.get('balance', 0) or 0 if user else 0
    
    category_name = CATEGORY_NAMES.get(category, category)
    text = (
        f"📦 <b>{category_name}</b>\n"
        f"{'━' * 25}\n\n"
        f"💰 <b>Ваш баланс:</b> {balance:.2f} USD\n\n"
        f"🛍️ <b>Товары в категории:</b>\n\n"
        f"Выберите товар для просмотра деталей:"
    )

    await callback.answer()
    await _edit(
        callback,
        owner_id,
        text,
        get_category_items_keyboard(category, owner_id),
    )


@router.callback_query(F.data.startswith("shop_item_"))
async def show_item_detail(callback: CallbackQuery):
                                                   
                                            
                                                                   
    data = callback.data.replace("shop_item_", "")
                                                                    
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
    
    item = SHOP_ITEMS.get(item_id)
    if not item:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return

    price_usd = float(get_item_price_usd(item_id) or 0)
    
                                 
    category = None
    for cat, items in SHOP_CATEGORIES.items():
        if item_id in items:
            category = cat
            break
    
    user = db.get_user(owner_id)
    balance = user.get('balance', 0) or 0 if user else 0
    
                                 
    effects_text = []
    if item.effects.get('hashrate', 0) > 0:
        effects_text.append(f"⚡ Хешрейт: +{item.effects['hashrate']} H/s")
    if item.effects.get('power_consumption', 0) > 0:
        effects_text.append(f"🔌 Потребление: +{item.effects['power_consumption']}W")
    if item.effects.get('heat', 0) > 0:
        effects_text.append(f"🌡️ Тепло: +{item.effects['heat']}°C")
    if item.effects.get('psu_power', 0) > 0:
        effects_text.append(f"⚡ Мощность БП: +{item.effects['psu_power']}W")
    if item.effects.get('cooling', 0) != 0:
        cooling = item.effects['cooling']
        effects_text.append(f"❄️ Охлаждение: {cooling}°C")
    
    effects_str = "\n".join(effects_text) if effects_text else "Нет эффектов"
    
    text = (
        f"🛍️ <b>{item.name}</b>\n"
        f"{'━' * 25}\n\n"
        f"💰 <b>Цена:</b> {price_usd:.0f} USD\n\n"
        f"📝 <b>Описание:</b>\n{item.description}\n\n"
        f"📊 <b>Характеристики:</b>\n{effects_str}\n\n"
        f"{'━' * 25}\n"
        f"💵 <b>Ваш баланс:</b> {balance:.2f} USD"
    )
    
    can_afford = balance >= price_usd
    if not can_afford:
        needed = price_usd - balance
        text += f"\n\n❌ <b>Недостаточно средств!</b>\n"
        text += f"💸 Нужно еще: {needed:.0f} USD"
    else:
        text += f"\n\n✅ <b>Достаточно средств для покупки</b>"

    await callback.answer()
    await _edit(callback, owner_id, text, get_item_detail_keyboard(item_id, owner_id, category))


@router.callback_query(F.data.startswith("buy_item_"))
async def buy_item_handler(callback: CallbackQuery):
                                                   
                                           
                                                                   
    data = callback.data.replace("buy_item_", "")
                                                                    
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
    
    success, message_text = buy_item(owner_id, item_id)
    
    if success:
        await callback.answer(message_text, show_alert=True)
                                         
        item = SHOP_ITEMS.get(item_id)
        if item:
                                         
            for cat, items in SHOP_CATEGORIES.items():
                if item_id in items:
                    category_name = CATEGORY_NAMES.get(cat, cat)
                    user = db.get_user(owner_id)
                    balance = user.get('balance', 0) or 0 if user else 0
                    text = (
                        f"📦 <b>{category_name}</b>\n"
                        f"{'━' * 25}\n\n"
                        f"💰 <b>Ваш баланс:</b> {balance:.2f} USD\n\n"
                        f"🛍️ <b>Товары в категории:</b>\n\n"
                        f"Выберите товар для просмотра деталей:"
                    )
                    await _edit(callback, owner_id, text, get_category_items_keyboard(cat, owner_id))
                    return
    else:
        await callback.answer(message_text, show_alert=True)
                                                                    
        item = SHOP_ITEMS.get(item_id)
        if item:
                                         
            category = None
            for cat, items in SHOP_CATEGORIES.items():
                if item_id in items:
                    category = cat
                    break
            
            user = db.get_user(owner_id)
            balance = user.get('balance', 0) or 0 if user else 0

            price_usd = float(get_item_price_usd(item_id) or 0)
            
            effects_text = []
            if item.effects.get('hashrate', 0) > 0:
                effects_text.append(f"⚡ Хешрейт: +{item.effects['hashrate']} H/s")
            if item.effects.get('power_consumption', 0) > 0:
                effects_text.append(f"🔌 Потребление: +{item.effects['power_consumption']}W")
            if item.effects.get('heat', 0) > 0:
                effects_text.append(f"🌡️ Тепло: +{item.effects['heat']}°C")
            if item.effects.get('psu_power', 0) > 0:
                effects_text.append(f"⚡ Мощность БП: +{item.effects['psu_power']}W")
            if item.effects.get('cooling', 0) != 0:
                cooling = item.effects['cooling']
                effects_text.append(f"❄️ Охлаждение: {cooling}°C")
            
            effects_str = "\n".join(effects_text) if effects_text else "Нет эффектов"
            
            text = (
                f"🛍️ <b>{item.name}</b>\n"
                f"{'━' * 25}\n\n"
                f"💰 <b>Цена:</b> {price_usd:.0f} USD\n\n"
                f"📝 <b>Описание:</b>\n{item.description}\n\n"
                f"📊 <b>Характеристики:</b>\n{effects_str}\n\n"
                f"{'━' * 25}\n"
                f"💵 <b>Ваш баланс:</b> {balance:.2f} USD"
            )
            
            can_afford = balance >= price_usd
            if not can_afford:
                needed = price_usd - balance
                text += f"\n\n❌ <b>Недостаточно средств!</b>\n"
                text += f"💸 Нужно еще: {needed:.0f} USD"
            else:
                text += f"\n\n✅ <b>Достаточно средств для покупки</b>"

            await _edit(callback, owner_id, text, get_item_detail_keyboard(item_id, owner_id, category))


@router.callback_query(F.data.startswith("back_to_shop_"))
async def back_to_shop(callback: CallbackQuery):
                                         
    try:
        owner_id = int(callback.data.replace("back_to_shop_", ""))
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
    
    balance = user.get('balance', 0) or 0
    
    shop_text = (
        f"🛒 <b>МАГАЗИН ОБОРУДОВАНИЯ</b>\n"
        f"{'━' * 25}\n\n"
        f"💰 <b>Ваш баланс:</b> {balance:.2f} USD\n\n"
        f"📦 <b>Доступные категории:</b>\n\n"
        f"Выберите категорию для просмотра товаров:"
    )
    
    await callback.answer()

    if callback.message is None or callback.message.chat is None:
        return
    set_ui_key_for_message(
        int(callback.message.chat.id),
        int(owner_id),
        int(callback.message.message_id),
        "shop",
    )

    shop_file_id = (db.get_setting("ui_image_shop", "") or "").strip()
    await _edit(
        callback,
        owner_id,
        shop_text,
        get_shop_categories_keyboard(owner_id),
        photo=(shop_file_id if shop_file_id else ""),
    )
