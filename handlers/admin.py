import asyncio
import time
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from database import db
from config import ADMIN_ID
from utils import send_notification, get_process_uptime_seconds, get_edit_debug_stats

router = Router()


@router.message(Command("ping"))
@router.message(F.text.startswith("/ping"))
async def cmd_ping(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    t0 = time.monotonic()
    await asyncio.sleep(0)
    loop_lag_ms = (time.monotonic() - t0) * 1000.0

    api_ms = None
    try:
        a0 = time.monotonic()
        await message.bot.get_me()
        api_ms = (time.monotonic() - a0) * 1000.0
    except Exception:
        api_ms = None

    db_ms = None
    try:
        d0 = time.monotonic()
        _ = db.get_stats()
        db_ms = (time.monotonic() - d0) * 1000.0
    except Exception:
        db_ms = None

    edit_stats = get_edit_debug_stats()
    uptime_s = get_process_uptime_seconds()

    lines = [
        "🏓 <b>PONG</b>",
        f"⏱ Uptime: <b>{uptime_s:.0f}s</b>",
        f"🌀 Event loop lag: <b>{loop_lag_ms:.1f} ms</b>",
        f"🤖 Telegram API latency: <b>{api_ms:.1f} ms</b>" if api_ms is not None else "🤖 Telegram API latency: <b>error</b>",
        f"🗄 DB latency: <b>{db_ms:.1f} ms</b>" if db_ms is not None else "🗄 DB latency: <b>error</b>",
        "", 
        "🧩 Edit throttling:",
        f"- ui_messages: <b>{edit_stats.get('ui_messages')}</b>",
        f"- message_locks: <b>{edit_stats.get('message_locks')}</b>",
        f"- chat_locks: <b>{edit_stats.get('chat_locks')}</b>",
        f"- rate_chats: <b>{edit_stats.get('rate_chats')}</b>",
        f"- min_wait_s: <b>{edit_stats.get('min_wait_s'):.3f}</b>",
        f"- max_wait_s: <b>{edit_stats.get('max_wait_s'):.3f}</b>",
    ]

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("reset_pending"))
@router.message(F.text.startswith("/reset_pending"))
async def cmd_reset_pending(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    affected = db.reset_all_pending_bitcoin()
    await message.answer(
        f"✅ pending_bitcoin обнулён у всех игроков.\n\n"
        f"Обновлено записей: {affected}",
        parse_mode="HTML",
    )


@router.message(Command("add_usd"))
@router.message(F.text.startswith("/add_usd "))
async def cmd_add_usd(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    command_text = message.text or ""
    parts = command_text.split()
    
    if len(parts) < 3:
        await message.answer(
            "❌ Неверный формат команды!\n\n"
            "Используйте: /add_usd [user_id] [amount]\n"
            "Пример: /add_usd 123456789 1000"
        )
        return
    
    try:
        target_user_id = int(parts[1])
        amount = float(parts[2])
        
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля!")
            return
        
        user = db.get_user(target_user_id)
        if not user:
            await message.answer(f"❌ Пользователь с ID {target_user_id} не найден.")
            return
        
        db.update_user_balance(target_user_id, amount)
        new_balance = (user.get('balance', 0) or 0) + amount
        
        await message.answer(
            f"✅ <b>USD добавлены!</b>\n\n"
            f"👤 Пользователь: {target_user_id}\n"
            f"💵 Добавлено: {amount:.2f} USD\n"
            f"💰 Новый баланс: {new_balance:.2f} USD",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "❌ Неверный формат!\n\n"
            "Используйте: /add_usd [user_id] [amount]\n"
            "user_id и amount должны быть числами."
        )


@router.message(Command("add_funds_all"))
@router.message(F.text.startswith("/add_funds_all"))
async def cmd_add_funds_all(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    usage_text = (
        "❌ Неверный формат команды!\n\n"
        "Используйте:\n"
        "/add_funds_all usd|btc <сумма> <причина>\n\n"
        "Примеры:\n"
        "/add_funds_all usd 100 Праздничный бонус\n"
        "/add_funds_all btc 0.001 Компенсация"
    )

    parts = (message.text or "").split(maxsplit=3)
                                                                        
    if len(parts) < 4:
        await message.answer(usage_text)
        return

    currency = parts[1].lower().strip()
    amount_str = parts[2].strip()
    reason = parts[3].strip()
    if not reason:
        await message.answer(usage_text)
        return

                  
    try:
        amount = float(amount_str.replace(",", "."))
    except ValueError:
        await message.answer(
            "❌ Сумма должна быть числом.\n\n" + usage_text
        )
        return

    if amount <= 0:
        await message.answer(
            "❌ Сумма должна быть больше нуля.\n\n" + usage_text
        )
        return

                           
    is_usd = currency in ("usd", "usdcoin", "u")
    is_btc = currency in ("btc", "bitcoin", "b")
    if not (is_usd or is_btc):
        await message.answer(
            "❌ Неизвестная валюта. Используйте usd или btc.\n\n" + usage_text
        )
        return

    users = db.get_all_users()
    if not users:
        await message.answer("ℹ️ В базе нет ни одного пользователя для выдачи.")
        return

    sent_count = 0
    for user in users:
        uid = user["user_id"]
                                                                                                        
        if is_usd:
            db.update_bank_balance(uid, amount)
            amount_display = f"{amount:.2f} USD"
        else:
            db.update_bank_bitcoin_balance(uid, amount)
            amount_display = f"{amount:.8f} BTC"

        text = (
            f"💰 <b>Вам начислена валюта!</b>\n\n"
            f"Вам были выданы {amount_display} администрацией.\n"
            f"Причина: {reason}\n\n"
            f"Валюта зачислена на ваш банковский счёт.\n"
            f"Приятной игры в <b>Mining Farm Simulator</b>!"
        )
        try:
            await send_notification(
                bot=message.bot,
                target_user_id=uid,
                notification_text=text,
                fallback_chat_id=None,
            )
            sent_count += 1
        except Exception:
                                                         
            continue

    await message.answer(
        f"✅ Массовая выдача выполнена.\n\n"
        f"Валюта: {'USD' if is_usd else 'BTC'}\n"
        f"Сумма на игрока: {amount_display}\n"
        f"Количество получателей: {len(users)}\n"
        f"Уведомления отправлены: {sent_count} игрокам.\n\n"
        f"Причина: {reason}",
        parse_mode="HTML",
    )


@router.message(Command("take_funds"))
@router.message(F.text.startswith("/take_funds "))
async def cmd_take_funds(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    parts = (message.text or "").split(maxsplit=4)
                                                                                  
    if len(parts) < 5:
        await message.answer(
            "❌ Неверный формат команды!\n\n"
            "Используйте: /take_funds &lt;валюта&gt; &lt;сумма&gt; &lt;user_id&gt; &lt;причина&gt;\n"
            "Пример:\n"
            "  /take_funds usd 500 123456789 Штраф за нарушение\n"
            "  /take_funds btc 0.001 123456789 Откат бага"
        )
        return

    currency = parts[1].lower()
    amount_str = parts[2]
    user_id_str = parts[3]
    reason = parts[4].strip()

                  
    try:
        amount = float(amount_str.replace(",", "."))
    except ValueError:
        await message.answer("❌ Сумма должна быть числом.")
        return

    if amount <= 0:
        await message.answer("❌ Сумма должна быть больше нуля.")
        return

                    
    try:
        target_user_id = int(user_id_str)
    except ValueError:
        await message.answer("❌ user_id должен быть числом.")
        return

    user = db.get_user(target_user_id)
    if not user:
        await message.answer(f"❌ Пользователь с ID {target_user_id} не найден.")
        return

    is_usd = currency in ("usd", "usdcoin", "u")
    is_btc = currency in ("btc", "bitcoin", "b")
    if not (is_usd or is_btc):
        await message.answer("❌ Неизвестная валюта. Используйте usd или btc.")
        return

                     
    balance = user.get("balance", 0) or 0
    bank_balance = user.get("bank_balance", 0) or 0
    btc_balance = user.get("bitcoin_balance", 0) or 0
    bank_btc_balance = user.get("bank_bitcoin_balance", 0) or 0

    if is_usd:
        total_available = balance + bank_balance
    else:
        total_available = btc_balance + bank_btc_balance

    if total_available < amount:
        await message.answer(
            "❌ Недостаточно средств у игрока для списания этой суммы.\n\n"
            f"Доступно всего: {total_available:.8f} {'USD' if is_usd else 'BTC'}."
        )
        return

                                                
    remaining = amount
    if is_usd:
                                      
        take_from_balance = min(balance, remaining)
        if take_from_balance > 0:
            db.update_user_balance(target_user_id, -take_from_balance)
            remaining -= take_from_balance

                                         
        if remaining > 0:
            db.update_bank_balance(target_user_id, -remaining)

        currency_label = "USD"
        taken_display = f"{amount:.2f} USD"
    else:
                                          
        take_from_btc = min(btc_balance, remaining)
        if take_from_btc > 0:
            db.update_bitcoin_balance(target_user_id, -take_from_btc)
            remaining -= take_from_btc

                                             
        if remaining > 0:
            db.update_bank_bitcoin_balance(target_user_id, -remaining)

        currency_label = "BTC"
        taken_display = f"{amount:.8f} BTC"

                        
    await message.answer(
        "✅ <b>Списание выполнено!</b>\n\n"
        f"👤 Пользователь: {target_user_id}\n"
        f"💸 Списано: {taken_display}\n"
        f"💱 Валюта: {currency_label}\n"
        f"📋 Причина: {reason}",
        parse_mode="HTML",
    )

                             
    notify_text = (
        "⚠️ <b>Списание средств администрацией</b>\n\n"
        f"С вашего аккаунта было списано: <b>{taken_display}</b>.\n"
        f"Причина: {reason}\n\n"
        "Если вы не согласны с решением, свяжитесь с администрацией."
    )

    await send_notification(
        bot=message.bot,
        target_user_id=target_user_id,
        notification_text=notify_text,
        fallback_chat_id=None,
        parse_mode="HTML",
    )


@router.message(Command("check_inv"))
@router.message(F.text.startswith("/check_inv"))
async def cmd_check_inv(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ Неверный формат команды!\n\n"
            "Используйте: /check_inv &lt;user_id&gt;\n"
            "Пример: /check_inv 123456789"
        )
        return

    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ user_id должен быть числом.")
        return

    user = db.get_user(target_user_id)
    if not user:
        await message.answer(f"❌ Пользователь с ID {target_user_id} не найден.")
        return

    inventory = db.get_user_inventory(target_user_id)
    if not inventory:
        await message.answer(
            f"🔍 <b>Инвентарь пользователя {target_user_id}</b>\n\n"
            "📭 Инвентарь пуст.",
            parse_mode="HTML",
        )
        return

                                                   
    lines: list[str] = []
    lines.append(f"🔍 <b>Инвентарь пользователя {target_user_id}</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━\n")

    from models import SHOP_ITEMS                               

    for idx, item in enumerate(inventory, start=1):
        inv_id = item.get("id")
        unique_id = item.get("unique_id")
        if not unique_id:
                                                                 
            new_uid = db._generate_unique_item_id()
            db.cursor.execute(
                "UPDATE inventory SET unique_id = ? WHERE id = ?",
                (new_uid, inv_id),
            )
            db.conn.commit()
            unique_id = new_uid

        item_id = item.get("item_id")
        item_name = item.get("item_name") or item_id
        item_type = item.get("item_type") or "unknown"
        qty = item.get("quantity", 0) or 0
        wear = item.get("wear", 100.0)
        is_broken = (item.get("is_broken", 0) or 0) == 1

                                                     
        shop_item = SHOP_ITEMS.get(item_id)
        if shop_item:
            item_name = shop_item.name

        status = "Сломано" if is_broken else "Исправно"

        lines.append(f"{idx}. <b>{item_name}</b> x{qty}")
        lines.append(f"   ID: <code>{unique_id}</code>")
        lines.append(f"   Тип: {item_type} | Состояние: {status}")
        if item_type in ("gpu", "asic", "psu"):
            lines.append(f"   Износ: {wear:.1f}%")
        lines.append("")

    text = "\n".join(lines).rstrip()

    await message.answer(text, parse_mode="HTML")


@router.message(Command("check_ob"))
@router.message(F.text.startswith("/check_ob"))
async def cmd_check_ob(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ Неверный формат команды!\n\n"
            "Используйте: /check_ob &lt;user_id&gt;\n"
            "Пример: /check_ob 123456789"
        )
        return

    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ user_id должен быть числом.")
        return

    user = db.get_user(target_user_id)
    if not user:
        await message.answer(f"❌ Пользователь с ID {target_user_id} не найден.")
        return

    installed = db.get_installed_items(target_user_id)
    if not installed:
        await message.answer(
            f"🔍 <b>Оборудование пользователя {target_user_id}</b>\n\n"
            "📭 На ферме нет установленного оборудования.",
            parse_mode="HTML",
        )
        return

    lines: list[str] = []
    lines.append(f"🔍 <b>Оборудование пользователя {target_user_id}</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━\n")

    from models import SHOP_ITEMS

    for idx, item in enumerate(installed, start=1):
        inst_id = item.get("id")
        unique_id = item.get("unique_id")
        if not unique_id:
            new_uid = db._generate_unique_item_id()
            db.cursor.execute(
                "UPDATE installed_items SET unique_id = ? WHERE id = ?",
                (new_uid, inst_id),
            )
            db.conn.commit()
            unique_id = new_uid

        item_id = item.get("item_id")
        item_name = item.get("item_name") or item_id
        item_type = item.get("item_type") or "unknown"
        qty = item.get("quantity", 0) or 0
        wear = item.get("wear", 100.0)

        shop_item = SHOP_ITEMS.get(item_id)
        if shop_item:
            item_name = shop_item.name

        lines.append(f"{idx}. <b>{item_name}</b> x{qty}")
        lines.append(f"   ID: <code>{unique_id}</code>")
        lines.append(f"   Тип: {item_type}")
        if item_type in ("gpu", "asic", "psu"):
            lines.append(f"   Износ: {wear:.1f}%")
        lines.append("")

    text = "\n".join(lines).rstrip()

    await message.answer(text, parse_mode="HTML")


@router.message(Command("take_ob"))
@router.message(F.text.startswith("/take_ob"))
async def cmd_take_ob(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ Неверный формат команды!\n\n"
            "Используйте: /take_ob &lt;unique_id&gt;\n"
            "Узнать ID предмета можно через /check_inv &lt;user_id&gt; или /check_ob &lt;user_id&gt;."
        )
        return

    unique_id = parts[1].strip()
    if not unique_id:
        await message.answer("❌ Укажите unique_id предмета.")
        return

                                     
    db.cursor.execute(
        "SELECT * FROM inventory WHERE unique_id = ?",
        (unique_id,),
    )
    row = db.cursor.fetchone()
    source = None
    item = None

    if row:
        item = dict(row)
        source = "inventory"
    else:
                                           
        db.cursor.execute(
            "SELECT * FROM installed_items WHERE unique_id = ?",
            (unique_id,),
        )
        row = db.cursor.fetchone()
        if row:
            item = dict(row)
            source = "installed"

    if not item:
        await message.answer(
            "❌ Предмет с таким ID не найден.\n"
            "Проверьте ID через /check_inv &lt;user_id&gt; или /check_ob &lt;user_id&gt; и попробуйте снова."
        )
        return

    target_user_id = item["user_id"]
    item_id = item.get("item_id")
    item_name = item.get("item_name") or item_id
    qty = item.get("quantity", 0) or 0

                                      
    if source == "inventory":
        db.cursor.execute(
            "DELETE FROM inventory WHERE id = ?",
            (item["id"],),
        )
        db.conn.commit()
        location = "инвентаря"
    else:
        db.cursor.execute(
            "DELETE FROM installed_items WHERE id = ?",
            (item["id"],),
        )
        db.conn.commit()
        location = "оборудования (фермы)"

                                                               
        from game_logic import calculate_user_stats, get_pending_bitcoin
        from datetime import datetime

        final_stats = calculate_user_stats(target_user_id)
        final_stats["pending_bitcoin"] = get_pending_bitcoin(target_user_id, update_db=False)
        final_stats["last_collect_time"] = datetime.now()
        db.update_user_stats(target_user_id, final_stats)

    await message.answer(
        "🧹 <b>Предмет удалён.</b>\n\n"
        f"👤 Пользователь: {target_user_id}\n"
        f"📦 Предмет: {item_name}\n"
        f"🔢 Количество: {qty}\n"
        f"📍 Источник: {location}\n"
        f"🆔 ID: <code>{unique_id}</code>",
        parse_mode="HTML",
    )



@router.message(Command("reset_account"))
@router.message(F.text.startswith("/reset_account"))
async def cmd_reset_account(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    command_text = message.text or ""
    parts = command_text.split()
    
                                                                                       
    if len(parts) >= 2:
        try:
            target_user_id = int(parts[1])
        except ValueError:
            await message.answer("❌ Неверный формат user_id!")
            return
    else:
        target_user_id = message.from_user.id
    
    user = db.get_user(target_user_id)
    if not user:
        await message.answer(f"❌ Пользователь с ID {target_user_id} не найден.")
        return
    
    db.reset_user_account(target_user_id)
    
    await message.answer(
        f"✅ <b>Аккаунт сброшен!</b>\n\n"
        f"👤 Пользователь: {target_user_id}\n"
        f"🔄 Все данные сброшены до начального состояния.",
        parse_mode="HTML"
    )


@router.message(Command("set_wallet_addres"))
@router.message(F.text.startswith("/set_wallet_addres"))
                                                          
@router.message(Command("set_wallet_address"))
@router.message(F.text.startswith("/set_wallet_address"))
async def cmd_set_wallet_address(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    command_text = message.text or ""
    parts = command_text.split()

    if len(parts) < 2:
        await message.answer(
            "❌ Неверный формат команды!\n\n"
            "Используйте:\n"
            "/set_wallet_addres <address>\n"
            "/set_wallet_addres <address> <user_id>\n\n"
            "Пример:\n"
            "/set_wallet_addres owner_name 123456789",
        )
        return

                                                                                               
    address = parts[1]
    import re
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,64}", address):
        await message.answer(
            "❌ Неверный формат адреса!\n"
            "Допустимы латиница, цифры, символы . _ - , длина 3–64."
        )
        return

                          
    if len(parts) >= 3:
        try:
            target_user_id = int(parts[2])
        except ValueError:
            await message.answer("❌ Неверный формат user_id!")
            return
    else:
        target_user_id = message.from_user.id

    user = db.get_user(target_user_id)
    if not user:
        await message.answer(f"❌ Пользователь с ID {target_user_id} не найден.")
        return

                                                 
    if db.is_wallet_address_taken(address, exclude_user_id=target_user_id):
        await message.answer("❌ Такой адрес уже используется другим игроком. Выберите другой.")
        return

    db.set_user_wallet_address(target_user_id, address)

    await message.answer(
        "✅ <b>Адрес кошелька обновлён!</b>\n\n"
        f"👤 Пользователь: {target_user_id}\n"
        f"🏷 Новый адрес: <code>{address}</code>",
        parse_mode="HTML",
    )


@router.message(Command("reset_wallet_addres"))
@router.message(F.text.startswith("/reset_wallet_addres"))
                                                  
@router.message(Command("reset_wallet_address"))
@router.message(F.text.startswith("/reset_wallet_address"))
async def cmd_reset_wallet_address(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    parts = (message.text or "").split()
    if len(parts) >= 2:
        try:
            target_user_id = int(parts[1])
        except ValueError:
            await message.answer("❌ Неверный формат user_id!")
            return
    else:
        target_user_id = message.from_user.id

    user = db.get_user(target_user_id)
    if not user:
        await message.answer(f"❌ Пользователь с ID {target_user_id} не найден.")
        return

                                                              
    import secrets
    import string
    alphabet = string.ascii_uppercase + string.digits
    def gen_addr():
        raw = "".join(secrets.choice(alphabet) for _ in range(16))
        return "-".join([raw[i:i+4] for i in range(0, 16, 4)])

                          
    new_address = gen_addr()
    while db.is_wallet_address_taken(new_address, exclude_user_id=target_user_id):
        new_address = gen_addr()

    db.set_user_wallet_address(target_user_id, new_address)

    await message.answer(
        "♻️ <b>Адрес кошелька сброшен</b>\n\n"
        f"👤 Пользователь: {target_user_id}\n"
        f"🏷 Новый адрес: <code>{new_address}</code>",
        parse_mode="HTML",
    )


@router.message(Command("bot_restart"))
@router.message(F.text.startswith("/bot_restart"))
async def cmd_bot_restart(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    await message.answer("♻️ Перезапуск бота инициирован...")

                                                                                
    import os, sys
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


@router.message(Command("tech"))
@router.message(F.text.startswith("/tech"))
async def cmd_tech(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    await message.answer("🛠 Бот уходит на техническое обслуживание...")

    import os, sys
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


@router.message(Command("ban_user"))
@router.message(F.text.startswith("/ban_user"))
async def cmd_ban_user(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    command_text = message.text or ""
    parts = command_text.split()

    reply_user = None
    if message.reply_to_message is not None:
        reply_user = getattr(message.reply_to_message, "from_user", None)

    if reply_user is None and len(parts) < 2:
        await message.answer(
            "❌ Неверный формат команды!\n\n"
            "Используйте:\n"
            "1) Ответом на сообщение: /ban_user [причина]\n"
            "2) По ID: /ban_user [user_id] [причина]\n\n"
            "Пример (reply): /ban_user Спам\n"
            "Пример (по ID): /ban_user 123456789 Нарушение правил"
        )
        return
    
    try:
        if reply_user is not None:
            target_user_id = int(reply_user.id)
            reason = " ".join(parts[1:]) if len(parts) > 1 else "Нарушение правил"
        else:
            target_user_id = int(parts[1])
            reason = " ".join(parts[2:]) if len(parts) > 2 else "Нарушение правил"
        
        if target_user_id == ADMIN_ID:
            await message.answer("❌ Нельзя заблокировать администратора!")
            return
        
        if db.is_user_banned(target_user_id):
            await message.answer(f"⚠️ Пользователь {target_user_id} уже заблокирован.")
            return
        
        db.ban_user(target_user_id, reason)
        
        await message.answer(
            f"🔨 <b>Пользователь заблокирован!</b>\n\n"
            f"👤 Пользователь: {target_user_id}\n"
            f"📋 Причина: {reason}",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "❌ Неверный формат!\n\n"
            "Используйте: /ban_user [user_id] [причина]\n"
            "user_id должен быть числом."
        )


@router.message(Command("unban_user"))
@router.message(F.text.startswith("/unban_user"))
async def cmd_unban_user(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    command_text = message.text or ""
    parts = command_text.split()
    
    if len(parts) < 2:
        await message.answer(
            "❌ Неверный формат команды!\n\n"
            "Используйте: /unban_user [user_id]\n"
            "Пример: /unban_user 123456789"
        )
        return
    
    try:
        target_user_id = int(parts[1])
        
        if not db.is_user_banned(target_user_id):
            await message.answer(f"ℹ️ Пользователь {target_user_id} не заблокирован.")
            return
        
        db.unban_user(target_user_id)
        
        await message.answer(
            f"✅ <b>Пользователь разблокирован!</b>\n\n"
            f"👤 Пользователь: {target_user_id}",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "❌ Неверный формат!\n\n"
            "Используйте: /unban_user [user_id]\n"
            "user_id должен быть числом."
        )


@router.message(Command("stats"))
@router.message(F.text.startswith("/stats"))
async def cmd_stats(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    stats = db.get_stats()

    from exchange_rate import get_bitcoin_exchange_rate
    rate = get_bitcoin_exchange_rate()
    
                                
    x2_mode = db.is_x2_mode_enabled()
    x2_weekend = db.is_x2_weekend_mode_enabled()
    x2_newyear = db.is_x2_newyear_mode_enabled()
    current_multiplier = db.get_current_hashrate_multiplier()
    
    x2_status = ""
    if x2_mode:
        x2_status = "🔥 X2 (постоянный)"
    elif x2_newyear:
        x2_status = "🎄 X2 (новогодний)"
    elif x2_weekend:
        if current_multiplier > 1:
            x2_status = "🔥 X2 (выходные - АКТИВЕН)"
        else:
            x2_status = "⏰ X2 (выходные - ожидание)"
    else:
        x2_status = "❌ Выключен"

    text = (
        "📊 <b>СТАТИСТИКА БОТА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👥 <b>Пользователи:</b>\n"
        f"• Всего игроков: {stats['users_count']}\n"
        f"• Активные майнеры: {stats['active_miners']}\n"
        f"• Заблокировано: {stats['banned_count']}\n\n"
        "💬 <b>Чаты:</b>\n"
        f"• Всего чатов: {stats['chats_count']}\n"
        f"• Групповых: {stats['groups_count']}\n"
        f"• Приватных: {stats['private_count']}\n\n"
        "💰 <b>Экономика:</b>\n"
        f"• Всего USD в системе: {stats['total_usd']:.2f} USD\n"
        f"• Всего BTC в системе: {stats['total_btc']:.8f} BTC\n"
        f"• Курс BTC: {rate:.2f} USD\n\n"
        "📦 <b>Предметы:</b>\n"
        f"• В инвентарях: {stats['inventory_items']} шт.\n"
        f"• Установлено на фермах: {stats['installed_items']} шт.\n\n"
        "⚡ <b>Режим X2:</b>\n"
        f"• Статус: {x2_status}\n"
        f"• Текущий множитель: x{current_multiplier:.0f}\n"
    )

                                   
    chats = db.get_all_chats()
    if chats:
        text += "\n💬 <b>Список чатов, где есть бот:</b>\n"
                                                                           
        max_chats_to_show = 30
        for idx, chat in enumerate(chats[:max_chats_to_show], start=1):
            chat_id = chat.get("chat_id")
            chat_type = chat.get("chat_type") or "unknown"
            title = (chat.get("title") or "").strip()
            username = (chat.get("username") or "").strip().lstrip("@")
            invite_link = (chat.get("invite_link") or "").strip()

            if chat_type in ("group", "supergroup"):
                chat_label = title or "(без названия группы)"
                if username:
                    chat_label += f" — <a href=\"https://t.me/{username}\">@{username}</a>"
                elif invite_link:
                    chat_label += f" — <a href=\"{invite_link}\">invite</a>"
            elif chat_type == "private":
                if username:
                    chat_label = f"(личный чат) — <a href=\"https://t.me/{username}\">@{username}</a>"
                else:
                    chat_label = f"(личный чат) — <a href=\"tg://user?id={chat_id}\">ссылка</a>"
            else:
                chat_label = f"({chat_type})"

            if chat_type not in ("private", "group", "supergroup") and username:
                chat_label += f" — <a href=\"https://t.me/{username}\">@{username}</a>"
            elif chat_type not in ("private", "group", "supergroup") and invite_link:
                chat_label += f" — <a href=\"{invite_link}\">invite</a>"

            text += f"• {idx}. <code>{chat_id}</code> — {chat_label}\n"

        if len(chats) > max_chats_to_show:
            remaining = len(chats) - max_chats_to_show
            text += f"… и ещё {remaining} чатов.\n"

    await message.answer(text, parse_mode="HTML")


                                                             

@router.message(Command("x2_on"))
@router.message(F.text.startswith("/x2_on"))
async def cmd_x2_on(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    db.set_x2_mode(True)
    
                         
    chats = db.get_all_chats()
    notify_text = "🔥 <b>РЕЖИМ X2 АКТИВИРОВАН!</b>\n\nХешрейт всех ферм увеличен в 2 раза! Приятного майнинга!"
    
    for chat in chats:
        try:
            await message.bot.send_message(chat_id=chat["chat_id"], text=notify_text, parse_mode="HTML")
        except Exception:
            continue
    
    await message.answer(
        "✅ <b>Режим X2 включён!</b>\n\n"
        "🔥 Хешрейт всех ферм увеличен в 2 раза.\n"
        "📢 Все чаты уведомлены.",
        parse_mode="HTML"
    )


@router.message(Command("x2_off"))
@router.message(F.text.startswith("/x2_off"))
async def cmd_x2_off(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    db.set_x2_mode(False)
    
                         
    chats = db.get_all_chats()
    notify_text = "⏸️ <b>Режим X2 завершён.</b>\n\nХешрейт ферм вернулся к обычным значениям."
    
    for chat in chats:
        try:
            await message.bot.send_message(chat_id=chat["chat_id"], text=notify_text, parse_mode="HTML")
        except Exception:
            continue
    
    await message.answer(
        "✅ <b>Режим X2 выключен!</b>\n\n"
        "⏸️ Хешрейт ферм вернулся к обычным значениям.\n"
        "📢 Все чаты уведомлены.",
        parse_mode="HTML"
    )


@router.message(Command("x2_weekend_on"))
@router.message(F.text.startswith("/x2_weekend_on"))
async def cmd_x2_weekend_on(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    db.set_x2_weekend_mode(True)
    
                                              
    from datetime import datetime
    weekday = datetime.now().weekday()
    is_weekend = weekday in (5, 6)
    
                         
    chats = db.get_all_chats()
    if is_weekend:
        notify_text = "🔥 <b>РЕЖИМ X2 ВЫХОДНОГО ДНЯ АКТИВИРОВАН!</b>\n\nХешрейт всех ферм увеличен в 2 раза до конца выходных!"
    else:
        notify_text = "⏰ <b>Режим X2 выходного дня включён!</b>\n\nВ субботу и воскресенье хешрейт всех ферм будет увеличен в 2 раза!"
    
    for chat in chats:
        try:
            await message.bot.send_message(chat_id=chat["chat_id"], text=notify_text, parse_mode="HTML")
        except Exception:
            continue
    
    status = "🔥 Активен прямо сейчас!" if is_weekend else "⏰ Активируется в субботу."
    
    await message.answer(
        "✅ <b>Режим X2 выходного дня включён!</b>\n\n"
        f"📅 Статус: {status}\n"
        "📢 Все чаты уведомлены.\n\n"
        "В субботу и воскресенье хешрейт всех ферм будет увеличен в 2 раза.",
        parse_mode="HTML"
    )


@router.message(Command("x2_weekend_off"))
@router.message(F.text.startswith("/x2_weekend_off"))
async def cmd_x2_weekend_off(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    db.set_x2_weekend_mode(False)
    
                         
    chats = db.get_all_chats()
    notify_text = "⏸️ <b>Режим X2 выходного дня отключён.</b>\n\nХешрейт ферм теперь не зависит от дня недели."
    
    for chat in chats:
        try:
            await message.bot.send_message(chat_id=chat["chat_id"], text=notify_text, parse_mode="HTML")
        except Exception:
            continue
    
    await message.answer(
        "✅ <b>Режим X2 выходного дня выключен!</b>\n\n"
        "⏸️ Хешрейт ферм больше не увеличивается в выходные.\n"
        "📢 Все чаты уведомлены.",
        parse_mode="HTML"
    )


@router.message(Command("x2_newyear_on"))
@router.message(F.text.startswith("/x2_newyear_on"))
async def cmd_x2_newyear_on(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    db.set_x2_newyear_mode(True)
    
                                                   
    chats = db.get_all_chats()
    notify_text = (
        "🎄🎅🎁 <b>С НОВЫМ ГОДОМ!</b> 🎁🎅🎄\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🥳 <b>Праздничный режим X2 активирован!</b>\n\n"
        "✨ В честь Нового Года хешрейт\n"
        "всех майнинг-ферм увеличен в <b>2 раза</b>!\n\n"
        "🎆 Пусть этот год принесёт вам\n"
        "много биткойнов и удачи!\n\n"
        "❄️🎄 <i>С праздником, майнеры!</i> 🎄❄️\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔥 <b>РЕЖИМ X2 АКТИВЕН!</b> 🔥"
    )
    
    for chat in chats:
        try:
            await message.bot.send_message(chat_id=chat["chat_id"], text=notify_text, parse_mode="HTML")
        except Exception:
            continue
    
    await message.answer(
        "🎄 <b>Новогодний режим X2 включён!</b> 🎄\n\n"
        "🔥 Хешрейт всех ферм увеличен в 2 раза.\n"
        "📢 Праздничное оповещение отправлено во все чаты.\n\n"
        "🎅 С Новым Годом!",
        parse_mode="HTML"
    )


@router.message(Command("x2_newyear_off"))
@router.message(F.text.startswith("/x2_newyear_off"))
async def cmd_x2_newyear_off(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    db.set_x2_newyear_mode(False)
    
                         
    chats = db.get_all_chats()
    notify_text = (
        "🎄 <b>Новогодние праздники закончились!</b> 🎄\n\n"
        "⏸️ Праздничный режим X2 отключён.\n"
        "Хешрейт ферм вернулся к обычным значениям.\n\n"
        "🎁 <i>Спасибо, что отмечали с нами!\n"
        "До новых праздников!</i> ✨"
    )
    
    for chat in chats:
        try:
            await message.bot.send_message(chat_id=chat["chat_id"], text=notify_text, parse_mode="HTML")
        except Exception:
            continue
    
    await message.answer(
        "✅ <b>Новогодний режим X2 выключен!</b>\n\n"
        "⏸️ Хешрейт ферм вернулся к обычным значениям.\n"
        "📢 Все чаты уведомлены.",
        parse_mode="HTML"
    )
