from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.filters import BaseFilter
from aiogram.exceptions import TelegramBadRequest
from database import db
from keyboards import get_wallet_keyboard
from game_logic import exchange_bitcoin_to_usd, collect_bitcoin
from exchange_rate import get_bitcoin_exchange_rate, get_bitcoin_last_update
from utils import (
    check_message_owner,
    handle_unauthorized_access,
    check_user_banned,
    render_ui_from_callback,
    render_ui_from_message,
    safe_edit_message_text,
    save_chat_from_message,
    save_chat_from_callback,
    set_ui_key_for_message,
)

router = Router()


_awaiting_btc_exchange: dict[int, dict[str, int]] = {}


class _AwaitingBtcExchangeFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if message.from_user is None:
            return False
        return int(message.from_user.id) in _awaiting_btc_exchange


def _build_wallet_text(owner_id: int) -> str:
    user = db.get_user(owner_id)
    if not user:
        return "❌ Пользователь не найден. Используйте /mining для регистрации."

    balance = user.get('balance', 0) or 0
    bitcoin_balance = user.get('bitcoin_balance', 0) or 0
    bank_balance = user.get('bank_balance', 0) or 0
    bank_bitcoin_balance = user.get('bank_bitcoin_balance', 0) or 0
    wallet_address, _ = db.ensure_user_wallet_addresses(owner_id)

    from game_logic import get_pending_bitcoin
    pending_btc = get_pending_bitcoin(owner_id, update_db=False)

    wallet_text = (
        f"💰 <b>КОШЕЛЕК</b>\n"
        f"{'━' * 25}\n\n"
        f"💵 <b>USD (на руках):</b> {balance:.2f} USD\n"
        f"₿ <b>Биткойн (на руках):</b> {bitcoin_balance:.8f} BTC\n\n"
        f"🏦 <b>БАНКОВСКОЕ ХРАНИЛИЩЕ</b>\n"
        f"💵 <b>В банке:</b> {bank_balance:.2f} USD\n"
        f"₿ <b>В банке:</b> {bank_bitcoin_balance:.8f} BTC\n\n"
        f"🏷 <b>Адрес кошелька для переводов между игроками:</b>\n"
        f"<code>{wallet_address}</code>\n"
    )

    if pending_btc > 0:
        wallet_text += f"\n💎 <b>Готово к сбору:</b> {pending_btc:.8f} BTC\n"

    rate = get_bitcoin_exchange_rate()
    wallet_text += f"\n{'━' * 25}\n"
    wallet_text += f"💱 <b>Курс обмена:</b> 1 BTC = {rate:.2f} USD\n"
    last_update_ts = get_bitcoin_last_update()
    if last_update_ts:
        from datetime import datetime

        dt = datetime.fromtimestamp(last_update_ts)
        wallet_text += f"⏱ <b>Обновлено:</b> {dt.strftime('%d.%m.%Y %H:%M')}\n\n"
    else:
        wallet_text += "\n"

    wallet_text += (
        f"💡 <i>Используйте кнопки ниже\n"
        f"для управления средствами</i>"
    )
    return wallet_text


@router.callback_query(F.data.startswith("main_wallet_"))
async def main_wallet_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                         
    try:
        owner_id = int(callback.data.replace("main_wallet_", ""))
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

    wallet_text = _build_wallet_text(owner_id)
    
    await callback.answer()

    if callback.message is None or callback.message.chat is None:
        return

    set_ui_key_for_message(
        int(callback.message.chat.id),
        int(owner_id),
        int(callback.message.message_id),
        "wallet",
    )

    wallet_file_id = (db.get_setting("ui_image_wallet", "") or "").strip()
    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=wallet_text,
        reply_markup=get_wallet_keyboard(owner_id),
        parse_mode="HTML",
        ui_key="wallet",
        photo=(wallet_file_id if wallet_file_id else ""),
    )


@router.message(Command("wallet"))
@router.message(F.text.startswith("/wallet"))
async def wallet_command(message: Message):
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
        await message.answer("❌ Пользователь не найден. Используйте /mining для регистрации.")
        return

    wallet_file_id = (db.get_setting("ui_image_wallet", "") or "").strip()
    wallet_text = _build_wallet_text(user_id)
    await render_ui_from_message(
        message=message,
        owner_id=user_id,
        text=wallet_text,
        reply_markup=get_wallet_keyboard(user_id),
        parse_mode="HTML",
        prefer_reply_in_groups=True,
        ui_key="wallet",
        photo=(wallet_file_id if wallet_file_id else ""),
    )


@router.callback_query(F.data.startswith("collect_bitcoin_"))
async def collect_bitcoin_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                         
    try:
        owner_id = int(callback.data.replace("collect_bitcoin_", ""))
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
    
                                            
    collected = collect_bitcoin(owner_id)
    
    if collected > 0:
        await callback.answer(f"✅ Собрано {collected:.8f} BTC!", show_alert=True)
    else:
        await callback.answer("ℹ️ Нет накопленного биткойна для сбора", show_alert=True)
    
                       
    await main_wallet_handler(callback)


@router.callback_query(F.data.startswith("exchange_bitcoin_"))
async def exchange_bitcoin_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                         
    try:
        owner_id = int(callback.data.replace("exchange_bitcoin_", ""))
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
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    bitcoin_balance = user.get('bitcoin_balance', 0) or 0
    
    if bitcoin_balance <= 0:
        await callback.answer("❌ У вас нет биткойна для обмена", show_alert=True)
        return

    if callback.message is not None:
        _awaiting_btc_exchange[owner_id] = {
            "chat_id": int(callback.message.chat.id),
            "message_id": int(callback.message.message_id),
        }
    else:
        _awaiting_btc_exchange[owner_id] = {}

    await callback.answer()

    prompt_text = (
        "✍️ <b>Обмен BTC → USD</b>\n\n"
        "Введите количество BTC для обмена.\n\n"
        "Напишите <code>all</code> — чтобы обменять всё,\n"
        "или число, например: <code>0.001</code>\n\n"
        f"Доступно: <b>{bitcoin_balance:.8f} BTC</b>"
    )
    prompt_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к ферме", callback_data=f"back_to_farm_{owner_id}")],
        ]
    )
    if callback.message is None or callback.message.chat is None:
        return
    await safe_edit_message_text(
        bot=callback.bot,
        chat_id=int(callback.message.chat.id),
        message_id=int(callback.message.message_id),
        text=prompt_text,
        reply_markup=prompt_kb,
        parse_mode="HTML",
    )


@router.message(_AwaitingBtcExchangeFilter(), F.text)
async def exchange_bitcoin_amount_message(message: Message):
    owner_id = int(message.from_user.id)
    ctx = _awaiting_btc_exchange.pop(owner_id, {})

    text = (message.text or "").strip()
    text_l = text.lower()
    if text_l in ("cancel", "отмена"):
        await message.answer("ℹ️ Обмен отменён.")
        return

    user = db.get_user(owner_id)
    if not user:
        await message.answer("❌ Пользователь не найден. Используйте /mining для регистрации.")
        return

    bitcoin_balance = float(user.get("bitcoin_balance", 0) or 0)
    if bitcoin_balance <= 0:
        await message.answer("❌ У вас нет биткойна для обмена")
        return

    if text_l == "all":
        amount = bitcoin_balance
    else:
        try:
            amount = float(text.replace(",", "."))
        except ValueError:
            await message.answer(
                "❌ Неверное значение. Напишите <code>all</code> или число, например <code>0.001</code>.",
                parse_mode="HTML",
            )
            return

    if amount <= 0:
        await message.answer("❌ Количество BTC должно быть больше нуля.")
        return

    if amount > bitcoin_balance:
        await message.answer(
            f"❌ Недостаточно BTC. Доступно: {bitcoin_balance:.8f} BTC",
        )
        return

    success, message_text, _usd_amount = exchange_bitcoin_to_usd(owner_id, amount)
    await message.answer(message_text)

    chat_id = ctx.get("chat_id")
    message_id = ctx.get("message_id")
    if chat_id and message_id:
        await safe_edit_message_text(
            bot=message.bot,
            chat_id=int(chat_id),
            message_id=int(message_id),
            text=_build_wallet_text(owner_id),
            reply_markup=get_wallet_keyboard(owner_id),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("buy_bitcoin_"))
async def buy_bitcoin_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
    try:
        owner_id = int(callback.data.replace("buy_bitcoin_", ""))
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

    user = db.get_user(owner_id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    balance = user.get("balance", 0) or 0
    if balance <= 0:
        await callback.answer("ℹ️ У вас нет USD для покупки BTC", show_alert=True)
        return

    rate = get_bitcoin_exchange_rate()
    if rate <= 0:
        await callback.answer("❌ Курс обмена недоступен. Попробуйте позже.", show_alert=True)
        return

                                               
    btc_amount = balance / rate

    from database import db as _db
                                                      
    _db.set_user_balance(owner_id, 0)                                
    _db.update_bitcoin_balance(owner_id, btc_amount)

    await callback.answer(
        f"✅ Куплено {btc_amount:.8f} BTC за {balance:.2f} USD по курсу {rate:.2f} USD за 1 BTC.",
        show_alert=True,
    )
    await main_wallet_handler(callback)


                                        


@router.callback_query(F.data.startswith("wallet_deposit_usd_"))
async def wallet_deposit_usd_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                         
    try:
        owner_id = int(callback.data.replace("wallet_deposit_usd_", ""))
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
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    balance = user.get("balance", 0) or 0
    if balance <= 0:
        await callback.answer("ℹ️ На обычном балансе нет средств для перевода в банк.", show_alert=True)
        return

    db.move_all_balance_to_bank(owner_id)
    await callback.answer(f"🏦 Весь баланс {balance:.2f} USD переведен в банк.", show_alert=True)
    await main_wallet_handler(callback)


@router.callback_query(F.data.startswith("wallet_withdraw_usd_"))
async def wallet_withdraw_usd_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                         
    try:
        owner_id = int(callback.data.replace("wallet_withdraw_usd_", ""))
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
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    bank_balance = user.get("bank_balance", 0) or 0
    if bank_balance <= 0:
        await callback.answer("ℹ️ В банке нет USD для вывода.", show_alert=True)
        return

    db.withdraw_all_from_bank(owner_id)
    await callback.answer(f"🏧 Снято из банка {bank_balance:.2f} USD на обычный баланс.", show_alert=True)
    await main_wallet_handler(callback)


@router.callback_query(F.data.startswith("wallet_deposit_btc_"))
async def wallet_deposit_btc_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                         
    try:
        owner_id = int(callback.data.replace("wallet_deposit_btc_", ""))
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
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    btc_balance = user.get("bitcoin_balance", 0) or 0
    if btc_balance <= 0:
        await callback.answer("ℹ️ На обычном BTC-балансе нет средств для перевода в банк.", show_alert=True)
        return

    db.move_all_bitcoin_to_bank(owner_id)
    await callback.answer(f"🏦 Весь баланс {btc_balance:.8f} BTC переведен в банк.", show_alert=True)
    await main_wallet_handler(callback)


@router.callback_query(F.data.startswith("wallet_withdraw_btc_"))
async def wallet_withdraw_btc_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                         
    try:
        owner_id = int(callback.data.replace("wallet_withdraw_btc_", ""))
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
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    bank_btc = user.get("bank_bitcoin_balance", 0) or 0
    if bank_btc <= 0:
        await callback.answer("ℹ️ В банке нет BTC для вывода.", show_alert=True)
        return

    db.withdraw_all_bitcoin_from_bank(owner_id)
    await callback.answer(f"🏧 Снято из банка {bank_btc:.8f} BTC на обычный баланс.", show_alert=True)
    await main_wallet_handler(callback)

