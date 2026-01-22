from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove, ChatMemberUpdated
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from keyboards import get_mining_farm_keyboard, get_back_to_farm_keyboard
from utils import (
    check_message_owner,
    handle_unauthorized_access,
    check_user_banned,
    save_chat_from_message,
    save_chat_from_callback,
    render_ui_from_callback,
    set_ui_key_for_message,
)
from config import ADMIN_ID
from database import db
from exchange_rate import get_bitcoin_exchange_rate

router = Router()


@router.message(Command("start"))
@router.message(F.text.startswith("/start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    save_chat_from_message(message)
    
                                                                                                  
    is_banned, ban_reason = check_user_banned(user_id)
    if is_banned:
        await message.answer(
            f"🚫 <b>Ваш аккаунт заблокирован!</b>\n\n"
            f"📋 <b>Причина блокировки:</b> {ban_reason}\n\n"
            f"💬 Для разблокировки обратитесь к администратору.",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML"
        )
        return
    
                                                           
    await message.answer(
        "👋 Добро пожаловать в майнинг-ферму!\n\n"
        "Используйте команду /mining для начала игры.\n"
        "Полный список команд: /help",
        reply_markup=ReplyKeyboardRemove()
    )


def _build_help_text(user_id: int | None = None) -> str:
    is_admin = user_id == ADMIN_ID if user_id is not None else False

    base_text = (
        "📖 <b>Mining Farm — помощь</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🧾 <b>Основные команды</b>\n"
        "• /mining — панель фермы (вкл/выкл, обновить)\n"
        "• /shop — магазин оборудования\n"
        "• /inv — инвентарь (или /inventory)\n"
        "• /wallet — кошелёк и банк\n"
        "• /info — подробная информация о ферме\n"
        "• /wiki — энциклопедия оборудования\n"
        "• /leaders — топ игроков\n"
        "• /profile — ваш профиль\n\n"
        "🏴 <b>Кланы</b>\n"
        "• /clan — информация о вашем клане\n"
        "• /clan_create &lt;название&gt; — создать клан\n"
        "• /clan_invite — пригласить в клан (нужно ответить на сообщение игрока)\n"
        "  Также можно: <code>Отправить приглашение</code> (ответом на сообщение)\n\n"
        "💸 <b>Переводы</b>\n"
        "• /send &lt;валюта&gt; &lt;адрес&gt; &lt;сумма&gt; — перевод USD/BTC\n"
        "  Пример: <code>/send usd ADDR-abcdef123456 150</code>\n\n"
        "🚨 <b>Социальные</b>\n"
        "• /police — донос на игрока (ответом на его сообщение)\n\n"
        "⛏ <b>Как запустить майнинг (шаги)</b>\n"
        "1) Купите в /shop: корпус (каркас GPU или стойку ASIC), устройство (GPU/ASIC) и БП, а так же Охлаждение\n"
        "2) Откройте /inv и установите предметы на ферму\n"
        "3) Откройте /mining и включите майнинг\n\n"
    )

    admin_text = (
        "🛠 <b>Админ-команды:</b>\n"
        "• /add_usd, /add_funds_all — выдать валюту\n"
        "• /take_funds &lt;валюта&gt; &lt;сумма&gt; &lt;user_id&gt; &lt;причина&gt; — отнять валюту\n"
        "• /check_inv &lt;user_id&gt; — посмотреть инвентарь игрока (с ID предметов)\n"
        "• /check_ob &lt;user_id&gt; — посмотреть оборудование игрока (с ID предметов)\n"
        "• /take_ob &lt;unique_id&gt; — удалить предмет по ID (инвентарь/оборудование)\n"
        "• /reset_account — сброс аккаунта\n"
        "• /set_wallet_addres, /reset_wallet_addres — управление кошельком\n"
        "• /stats — статистика бота\n"
        "• /bot_restart, /tech — рестарт / техработы\n"
        "• /ban_user, /unban_user — бан / разбан\n"
        "• /x2_on, /x2_off — постоянный X2\n"
        "• /x2_weekend_on, /x2_weekend_off — X2 по выходным\n"
        "• /x2_newyear_on, /x2_newyear_off — новогодний X2\n\n"
    )

    footer = "📨 Связь с разработчиками в Telegram: Сообщить о баге, получить помощь по тех.части: @synckz | Вопросы и предложения (в том числе и реклама): @pLegx"

    return base_text + (admin_text if is_admin else "") + footer


@router.message(Command("help"))
@router.message(F.text.startswith("/help"))
async def cmd_help_command(message: Message):
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
    
    await message.answer(_build_help_text(message.from_user.id), parse_mode="HTML")


@router.callback_query(F.data.startswith("main_help_"))
async def cmd_help_callback(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                         
    try:
        owner_id = int(callback.data.replace("main_help_", ""))
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
    
    await callback.answer()
    
    help_text = _build_help_text(callback.from_user.id)

    if callback.message is None or callback.message.chat is None:
        return

    chat_id = int(callback.message.chat.id)
    message_id = int(callback.message.message_id)
    set_ui_key_for_message(chat_id, int(owner_id), message_id, "menu")

    menu_file_id = (db.get_setting("ui_image_menu", "") or "").strip()
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=help_text,
        reply_markup=get_back_to_farm_keyboard(owner_id),
        parse_mode="HTML",
        ui_key="menu",
        photo=(menu_file_id if menu_file_id else ""),
    )


@router.my_chat_member()
async def my_chat_member_handler(event: ChatMemberUpdated):
    chat = getattr(event, "chat", None)
    if not chat:
        return

    chat_id = chat.id
    chat_type = chat.type
    title = chat.title or ""
    username = getattr(chat, "username", None) or ""

    invite_link = getattr(event, "invite_link", None)
    invite_link_str = getattr(invite_link, "invite_link", None) or ""

    new_member = getattr(event, "new_chat_member", None)
    status = getattr(new_member, "status", None)
    if status in ("member", "administrator"):
        db.add_chat_if_not_exists(
            chat_id,
            chat_type,
            title,
            username=username,
            invite_link=invite_link_str,
        )
