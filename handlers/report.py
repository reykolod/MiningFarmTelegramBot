from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from database import db
from utils import send_notification, check_user_banned
from datetime import datetime
import random


router = Router()


@router.message(Command("police"))
@router.message(F.text.lower() == "позвонить в полицию")
async def report_player_command(message: Message):
                                           
    if not message.reply_to_message:
        await message.reply(
            "🚨 <b>Как позвонить в полицию:</b>\n\n"
            "Ответьте на сообщение игрока, на которого хотите донести, "
            "командой /police или текстом «Позвонить в полицию».",
            parse_mode="HTML"
        )
        return
    
                                      
    if message.chat.type == "private":
        await message.reply("🚫 Донос работает только в групповых чатах.", parse_mode="HTML")
        return
    
    reporter_id = message.from_user.id
    target_message = message.reply_to_message
    
                                                  
    if target_message.from_user.is_bot:
        await message.reply("🤖 Нельзя доносить на ботов.", parse_mode="HTML")
        return
    
    target_id = target_message.from_user.id
    
                                       
    if reporter_id == target_id:
        await message.reply("🤔 Нельзя доносить на самого себя.", parse_mode="HTML")
        return
    
                                    
    is_banned, ban_reason = check_user_banned(reporter_id)
    if is_banned:
        await message.reply(
            f"🚫 <b>Ваш аккаунт заблокирован!</b>\n\n"
            f"📋 <b>Причина:</b> {ban_reason}",
            parse_mode="HTML"
        )
        return
    
    reporter = db.get_user(reporter_id)
    target = db.get_user(target_id)
    
    if not reporter:
        await message.reply(
            "❌ Для начала зарегистрируйтесь командой /mining.",
            parse_mode="HTML"
        )
        return
    
    if not target:
        await message.reply(
            "❌ Игрок, на которого вы пытаетесь донести, не зарегистрирован в игре.",
            parse_mode="HTML"
        )
        return
    
                                                      
    last_report_time = db.get_last_report_time(reporter_id)
    if last_report_time:
        time_since_last_report = datetime.now() - (
            last_report_time if isinstance(last_report_time, datetime) 
            else datetime.fromisoformat(str(last_report_time))
        )
        hours_remaining = 24 - (time_since_last_report.total_seconds() / 3600)
        
        if hours_remaining > 0:
            hours = int(hours_remaining)
            minutes = int((hours_remaining - hours) * 60)
            await message.reply(
                f"⏰ <b>Вы уже звонили в полицию недавно!</b>\n\n"
                f"⏳ До следующего звонка осталось: {hours}ч {minutes}м",
                parse_mode="HTML"
            )
            return
    
    reporter_username = reporter.get('username', 'Неизвестный') or f"ID: {reporter_id}"
    target_username = target.get('username', 'Неизвестный') or f"ID: {target_id}"
    
                     
    roll = random.random()
    success = roll < 0.10
    
    if success:
                                                              
        target_balance = target.get("balance", 0) or 0
        if target_balance <= 0:
                                        
            await send_notification(
                bot=message.bot,
                target_user_id=reporter_id,
                notification_text=(
                    "👮 <b>Результат вызова полиции</b>\n\n"
                    f"📋 Цель: {target_username}\n"
                    "❌ Полиция приехала, но у цели пустой баланс — нечего конфисковать."
                ),
                fallback_chat_id=None                                    
            )
                                      
            await message.reply("👮 Полиция приехала, но нарушений не обнаружила.", parse_mode="HTML")
            db.update_last_report_time(reporter_id)
            return
        
                         
        confiscation = target_balance * 0.20
        reward = confiscation                                            
        
                          
        db.update_user_balance(target_id, -confiscation)
                              
        db.update_user_balance(reporter_id, reward)
        
        new_reporter_balance = (reporter.get("balance", 0) or 0) + reward
        new_target_balance = target_balance - confiscation
        
                                    
        reporter_notification = (
            f"👮 <b>УСПЕШНЫЙ ДОНОС!</b>\n\n"
            f"📋 <b>Цель:</b> {target_username}\n\n"
            f"💰 <b>Результат:</b>\n"
            f"• Конфисковано у цели: {confiscation:.2f} USD (20%)\n"
            f"• Ваша награда: +{reward:.2f} USD\n\n"
            f"💵 <b>Ваш новый баланс:</b> {new_reporter_balance:.2f} USD"
        )
        await send_notification(
            bot=message.bot,
            target_user_id=reporter_id,
            notification_text=reporter_notification,
            fallback_chat_id=None
        )
        
                                 
        target_notification = (
            f"🚨 <b>ВНИМАНИЕ! ПОЛИЦЕЙСКИЙ РЕЙД!</b>\n\n"
            f"👮 На вас поступил донос!\n\n"
            f"📋 <b>Детали:</b>\n"
            f"• Доносчик: {reporter_username}\n"
            f"• Конфисковано: {confiscation:.2f} USD (20%)\n"
            f"• Банковские счета не затронуты\n\n"
            f"💰 <b>Новый баланс:</b> {new_target_balance:.2f} USD"
        )
        await send_notification(
            bot=message.bot,
            target_user_id=target_id,
            notification_text=target_notification,
            fallback_chat_id=None
        )
        
                                  
        await message.reply(
            f"🚨 Полиция провела рейд! Нарушения обнаружены.",
            parse_mode="HTML"
        )
        
    else:
                                                                
        reporter_balance = reporter.get("balance", 0) or 0
        if reporter_balance <= 0:
                              
            await send_notification(
                bot=message.bot,
                target_user_id=reporter_id,
                notification_text=(
                    "⚖️ <b>Результат вызова полиции</b>\n\n"
                    f"📋 Цель: {target_username}\n"
                    "❌ Ложный вызов! Но штраф не применён — у вас пустой баланс."
                ),
                fallback_chat_id=None
            )
                                      
            await message.reply("👮 Полиция приехала, но нарушений не обнаружила.", parse_mode="HTML")
            db.update_last_report_time(reporter_id)
            return
        
        fine = reporter_balance * 0.10
        db.update_user_balance(reporter_id, -fine)
        
        new_reporter_balance = reporter_balance - fine
        
                                    
        reporter_notification = (
            f"⚖️ <b>ЛОЖНЫЙ ВЫЗОВ!</b>\n\n"
            f"📋 <b>Цель:</b> {target_username}\n\n"
            f"❌ Полиция не нашла нарушений.\n\n"
            f"💸 <b>Штраф за ложный вызов:</b>\n"
            f"• Списано: {fine:.2f} USD (10%)\n\n"
            f"💵 <b>Ваш новый баланс:</b> {new_reporter_balance:.2f} USD"
        )
        await send_notification(
            bot=message.bot,
            target_user_id=reporter_id,
            notification_text=reporter_notification,
            fallback_chat_id=None
        )
        
                               
        target_notification = (
            f"🛡️ <b>Защита сработала!</b>\n\n"
            f"⚖️ На вас поступил ложный донос, который был отклонен.\n\n"
            f"📋 <b>Детали:</b>\n"
            f"• Доносчик: {reporter_username}\n"
            f"• Доносчик получил штраф: {fine:.2f} USD\n\n"
            f"✅ Ваши средства в безопасности!"
        )
        await send_notification(
            bot=message.bot,
            target_user_id=target_id,
            notification_text=target_notification,
            fallback_chat_id=None
        )
        
                                  
        await message.reply(
            f"👮 Полиция приехала, но нарушений не обнаружила.",
            parse_mode="HTML"
        )
    
                                       
    db.update_last_report_time(reporter_id)
