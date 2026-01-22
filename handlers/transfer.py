from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from database import db
from utils import send_notification, check_user_banned


def get_sender_address(user_id: int) -> str:
    usd_address, _ = db.ensure_user_wallet_addresses(user_id)
    return usd_address or f"ID: {user_id}"


router = Router()


@router.message(Command("send"))
@router.message(F.text.startswith("/send"))
async def send_currency_command(message: Message):
    user_id = message.from_user.id
    
                          
    is_banned, ban_reason = check_user_banned(user_id)
    if is_banned:
        await message.answer(
            f"🚫 <b>Ваш аккаунт заблокирован!</b>\n\n"
            f"📋 <b>Причина блокировки:</b> {ban_reason}\n\n"
            f"💬 Для разблокировки обратитесь к администратору.",
            parse_mode="HTML"
        )
        return
    
    parts = (message.text or "").split()

    if len(parts) < 4:
        await message.answer(
            "❌ Неверный формат команды.\n\n"
            "Использование:\n"
            "/send &lt;валюта&gt; &lt;адрес&gt; &lt;сумма&gt;\n\n"
            "Примеры:\n"
            "/send usd ADDR-abcdef123456 100\n"
            "/send btc ADDR-abcdef123456 0.001",
            parse_mode="HTML",
        )
        return

    currency = parts[1].lower()
    address = parts[2]
    amount_str = parts[3]

                      
    if currency not in ("usd", "usdcoin", "u", "btc", "bitcoin", "b"):
        await message.answer("❌ Неизвестная валюта. Используйте usd или btc.")
        return

    amount: float
    amount_usd_int: int | None = None
    if currency in ("usd", "usdcoin", "u"):
        if not amount_str.isdigit():
            await message.answer("❌ USD можно переводить только целым числом (например: 1, 10, 250).")
            return
        amount_usd_int = int(amount_str)
        if amount_usd_int <= 0:
            await message.answer("❌ Сумма должна быть больше нуля.")
            return
        amount = float(amount_usd_int)
    else:
        amount_dec: Decimal
        try:
            amount_dec = Decimal(amount_str.replace(",", "."))
        except (InvalidOperation, ValueError):
            await message.answer("❌ Сумма должна быть числом.")
            return
        if amount_dec <= 0:
            await message.answer("❌ Сумма должна быть больше нуля.")
            return
        amount_dec = amount_dec.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        if amount_dec <= 0:
            await message.answer("❌ Сумма слишком маленькая. Минимум: 0.00000001 BTC")
            return
        amount = float(amount_dec)

    sender = db.get_user(user_id)
    if not sender:
        await message.answer("❌ Пользователь не найден. Используйте /mining для регистрации.")
        return

    created_at_raw = sender.get("created_at")
    created_at_dt = None
    if isinstance(created_at_raw, datetime):
        created_at_dt = created_at_raw
    elif isinstance(created_at_raw, str) and created_at_raw.strip():
        created_at_str = created_at_raw.strip()
        try:
            created_at_dt = datetime.fromisoformat(created_at_str)
        except ValueError:
            try:
                created_at_dt = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                created_at_dt = None

    if created_at_dt is not None:
        now = datetime.utcnow()
        if now < created_at_dt:
            created_at_dt = None
        else:
            cooldown = timedelta(hours=24)
            passed = now - created_at_dt
            if passed < cooldown:
                remaining = cooldown - passed
                total_minutes = int(remaining.total_seconds() // 60)
                hours_left = total_minutes // 60
                minutes_left = total_minutes % 60
                await message.answer(
                    "⏳ Переводы для новых игроков доступны через 24 часа после создания фермы.\n\n"
                    f"Осталось: {hours_left}ч {minutes_left}м."
                )
                return

                                                
    receiver = db.get_user_by_usd_address(address)
    if not receiver:
        await message.answer("❌ Получатель с таким адресом кошелька не найден.")
        return

    receiver_id = receiver["user_id"]
    if receiver_id == user_id:
        await message.answer("🤔 Нельзя отправлять средства самому себе.")
        return

                 
    if currency in ("usd", "usdcoin", "u"):
        sender_balance = sender.get("balance", 0) or 0
        if sender_balance < amount:
            await message.answer(
                f"❌ Недостаточно средств.\n"
                f"Ваш баланс: {sender_balance:.2f} USD, нужно: {amount:.2f} USD."
            )
            return

                                                               
        db.update_user_balance(user_id, -amount)
        db.update_user_balance(receiver_id, amount)

        sender_username = sender.get('username', 'Неизвестный') or f"ID: {user_id}"
        sender_address = get_sender_address(user_id)
        receiver = db.get_user(receiver_id)
        receiver_balance = receiver.get("balance", 0) or 0 if receiver else 0

        await message.answer(
            f"✅ Перевод выполнен!\n\n"
            f"📤 Вы отправили {int(amount) if amount_usd_int is None else amount_usd_int} USD по адресу <code>{address}</code>.\n"
            f"💰 Новый баланс: {(sender_balance - amount):.2f} USD.",
            parse_mode="HTML",
        )
        
                                          
        receiver_notification = (
            f"💰 <b>Получен перевод!</b>\n\n"
            f"📥 Вы получили перевод от пользователя {sender_username}\n\n"
            f"📋 <b>Детали:</b>\n"
            f"• Сумма: {int(amount) if amount_usd_int is None else amount_usd_int} USD\n"
            f"• Адрес отправителя: <code>{sender_address}</code>\n"
            f"• Валюта: USD\n\n"
            f"💰 <b>Новый баланс:</b> {receiver_balance:.2f} USD"
        )
        
        await send_notification(
            bot=message.bot,
            target_user_id=receiver_id,
            notification_text=receiver_notification,
            fallback_chat_id=message.chat.id
        )
        return

                 
    sender_btc = sender.get("bitcoin_balance", 0) or 0
    sender_btc_dec = Decimal(str(sender_btc)).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
    amount_dec = Decimal(str(amount)).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)

    if amount_dec > sender_btc_dec:
                                                                  
        diff = amount_dec - sender_btc_dec
        if diff <= Decimal("0.00000001"):
            amount = float(sender_btc_dec)
            amount_dec = sender_btc_dec
        else:
            await message.answer(
                f"❌ Недостаточно средств.\n"
                f"Ваш BTC-баланс: {sender_btc_dec:.8f} BTC, нужно: {amount_dec:.8f} BTC."
            )
            return

    if amount_dec == sender_btc_dec:
                                                                  
        amount = float(sender_btc_dec)
        amount_dec = sender_btc_dec

    if float(sender_btc_dec) < float(amount_dec):
        await message.answer(
            f"❌ Недостаточно средств.\n"
            f"Ваш BTC-баланс: {sender_btc_dec:.8f} BTC, нужно: {amount_dec:.8f} BTC."
        )
        return

    db.update_bitcoin_balance(user_id, -amount)
    db.update_bitcoin_balance(receiver_id, amount)

    sender_username = sender.get('username', 'Неизвестный') or f"ID: {user_id}"
    sender_address = get_sender_address(user_id)
    receiver = db.get_user(receiver_id)
    receiver_btc = receiver.get("bitcoin_balance", 0) or 0 if receiver else 0

    await message.answer(
        f"✅ Перевод выполнен!\n\n"
        f"📤 Вы отправили {amount_dec:.8f} BTC по адресу <code>{address}</code>.\n"
        f"₿ Новый баланс: {(sender_btc_dec - amount_dec):.8f} BTC.",
        parse_mode="HTML",
    )
    
                                      
    receiver_notification = (
        f"₿ <b>Получен перевод!</b>\n\n"
        f"📥 Вы получили перевод от пользователя {sender_username}\n\n"
        f"📋 <b>Детали:</b>\n"
        f"• Сумма: {amount_dec:.8f} BTC\n"
        f"• Адрес отправителя: <code>{sender_address}</code>\n"
        f"• Валюта: Bitcoin (BTC)\n\n"
        f"₿ <b>Новый баланс:</b> {receiver_btc:.8f} BTC"
    )
    
    await send_notification(
        bot=message.bot,
        target_user_id=receiver_id,
        notification_text=receiver_notification,
        fallback_chat_id=message.chat.id
    )


