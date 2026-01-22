from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from database import db
from keyboards import get_wiki_categories_keyboard
from models import SHOP_CATEGORIES, CATEGORY_NAMES, SHOP_ITEMS, get_item_price_usd
from utils import (
    check_user_banned,
    check_message_owner,
    handle_unauthorized_access,
    render_ui_from_callback,
    render_ui_from_message,
    save_chat_from_message,
    save_chat_from_callback,
    set_ui_key_for_message,
    get_ui_key_for_message,
)

router = Router()


@router.message(Command("wiki"))
@router.message(F.text.startswith("/wiki"))
async def wiki_command(message: Message):
    user_id = message.from_user.id
    save_chat_from_message(message)

                          
    is_banned, ban_reason = check_user_banned(user_id)
    if is_banned:
        await message.answer(
            f"🚫 <b>Ваш аккаунт заблокирован!</b>\n\n"
            f"📋 <b>Причина блокировки:</b> {ban_reason}\n\n"
            f"💬 Для разблокировки обратитесь к администратору.",
            parse_mode="HTML",
        )
        return

    text = (
        "📚 <b>Энциклопедия оборудования</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Выберите категорию, чтобы посмотреть список всего оборудования и его характеристики."
    )

    wiki_file_id = (db.get_setting("ui_image_wiki", "") or "").strip()
    await render_ui_from_message(
        message=message,
        owner_id=user_id,
        text=text,
        reply_markup=get_wiki_categories_keyboard(user_id),
        parse_mode="HTML",
        disable_web_page_preview=True,
        prefer_reply_in_groups=True,
        ui_key="wiki",
        photo=(wiki_file_id if wiki_file_id else ""),
    )


@router.callback_query(F.data.startswith("main_wiki_"))
async def main_wiki_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
    try:
        owner_id = int(callback.data.replace("main_wiki_", ""))
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
        "📚 <b>Энциклопедия оборудования</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Выберите категорию, чтобы посмотреть список всего оборудования и его характеристики."
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
        reply_markup=get_wiki_categories_keyboard(owner_id, back_to_menu=True),
        parse_mode="HTML",
        disable_web_page_preview=True,
        ui_key="menu",
        photo=(menu_file_id if menu_file_id else ""),
    )


@router.callback_query(F.data.startswith("wiki_cat_"))
async def wiki_category_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)

                                            
    data = callback.data.replace("wiki_cat_", "")
    last_underscore = data.rfind("_")
    if last_underscore == -1:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

    category = data[:last_underscore]
    try:
        owner_id = int(data[last_underscore + 1 :])
    except ValueError:
        await callback.answer("❌ Ошибка данных. Обновите сообщение.", show_alert=True)
        return

                                     
    is_owner, _ = check_message_owner(callback, owner_id)
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

    if category not in SHOP_CATEGORIES:
        await callback.answer("❌ Неизвестная категория.", show_alert=True)
        return

    item_ids = SHOP_CATEGORIES.get(category, [])
    category_name = CATEGORY_NAMES.get(category, category)

    if callback.message is None or callback.message.chat is None:
        return

    chat_id = int(callback.message.chat.id)
    message_id = int(callback.message.message_id)
    current_key = (get_ui_key_for_message(chat_id, int(owner_id), message_id) or "").strip().lower()

    if current_key == "menu":
        target_key = "menu"
        file_id = (db.get_setting("ui_image_menu", "") or "").strip()
    else:
        target_key = "wiki"
        file_id = (db.get_setting(f"cat_image_{category}", "") or "").strip()

    set_ui_key_for_message(chat_id, int(owner_id), message_id, target_key)

    lines: list[str] = []
    lines.append("📚 <b>Энциклопедия оборудования</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"\n📂 <b>Категория:</b> {category_name}\n")

    if not item_ids:
        lines.append("В этой категории пока нет предметов.")
    else:
        for item_id in item_ids:
            item = SHOP_ITEMS.get(item_id)
            if not item:
                continue

            price_usd = float(get_item_price_usd(item_id) or 0)
            lines.append(f"🔹 <b>{item.name}</b> — {price_usd:.0f} USD")

            hashrate = item.effects.get("hashrate", 0)
            power = item.effects.get("power_consumption", 0)
            heat = item.effects.get("heat", 0)
            psu_power = item.effects.get("psu_power", 0)
            cooling = item.effects.get("cooling", 0)

                                                               
            if item.item_type == "rig":
                gpu_slots = getattr(item, "gpu_slots", 0) or 0
                if gpu_slots > 0:
                    lines.append(f"   • 🧩 Слотов для GPU: {gpu_slots}")
            if item.item_type == "asic_rig":
                asic_slots = getattr(item, "asic_slots", 0) or 0
                if asic_slots > 0:
                    lines.append(f"   • 🧩 Слотов для ASIC: {asic_slots}")

            if hashrate:
                lines.append(f"   • ⚡ Хешрейт: {hashrate} H/s")
            if power:
                lines.append(f"   • 🔌 Потребление: {power} W")
            if heat:
                lines.append(f"   • 🌡️ Тепло: {heat} °C")
            if psu_power:
                lines.append(f"   • ⚡ Мощность БП: {psu_power} W")
            if cooling:
                lines.append(f"   • ❄️ Охлаждение: {cooling} °C")

            lines.append("")                                  

    text = "\n".join(lines).rstrip()

    await callback.answer()
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=text,
        reply_markup=get_wiki_categories_keyboard(owner_id, back_to_menu=(target_key == "menu")),
        parse_mode="HTML",
        ui_key=target_key,
        photo=(file_id if file_id else ""),
    )


