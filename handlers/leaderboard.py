from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
import html
from database import db
from keyboards import get_leaderboard_keyboard
from exchange_rate import get_bitcoin_exchange_rate
from utils import (
    check_message_owner,
    handle_unauthorized_access,
    check_user_banned,
    render_ui_from_callback,
    render_ui_from_message,
    save_chat_from_message,
    save_chat_from_callback,
    set_ui_key_for_message,
    get_ui_key_for_message,
)

router = Router()


def _format_user_link(user_id: int, raw_username: str | None) -> str:
    if raw_username:
        display_name = raw_username if len(raw_username) <= 20 else raw_username[:17] + "..."
        return f'<a href="https://t.me/{raw_username}">{display_name}</a>'
    return f'<a href="tg://user?id={int(user_id)}">ID:{int(user_id)}</a>'


def format_leaderboard_wealth(top_players, user_id, owner_id):
    if not top_players:
        return (
            "🏆 <b>Топ самых богатых игроков</b>\n\n"
            "📊 Пока нет игроков в рейтинге.\n"
            "Начните играть, чтобы попасть в топ!"
        )
    
    leaderboard_text = "🏆 <b>Топ самых богатых игроков</b>\n"
    leaderboard_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
                     
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for idx, player in enumerate(top_players):
        position = idx + 1
        raw_username = player.get('username')
        if raw_username:
            display_name = raw_username if len(raw_username) <= 20 else raw_username[:17] + "..."
            username_display = f'<a href="https://t.me/{raw_username}">{display_name}</a>'
        else:
            display_name = f"ID:{player['user_id']}"
            username_display = f'<a href="tg://user?id={player["user_id"]}">{display_name}</a>'
        balance = player.get('balance', 0) or 0
        bitcoin_balance = player.get('bitcoin_balance', 0) or 0
        total_wealth = player.get('total_wealth', 0) or 0
        
                                   
        if position <= 10:
            medal = medals[idx]
        else:
            medal = f"{position}."
        
        leaderboard_text += f"{medal} <b>{username_display}</b>\n"
        leaderboard_text += f"   💰 Всего: {total_wealth:.2f} USD\n"
        leaderboard_text += f"   💵 USD: {balance:.2f} | ₿ BTC: {bitcoin_balance:.8f}\n\n"
    
                                                       
    current_user = db.get_user(user_id)
    if current_user:
        current_balance = current_user.get('balance', 0) or 0
        current_btc = current_user.get('bitcoin_balance', 0) or 0
        rate = get_bitcoin_exchange_rate()
        current_wealth = current_balance + current_btc * rate
        
                                         
        current_position = None
        for idx, player in enumerate(top_players):
            if player['user_id'] == user_id:
                current_position = idx + 1
                break
        
        if current_position is None:
                                                           
            current_position = db.get_user_position(user_id)
        
        if current_position:
            leaderboard_text += "━━━━━━━━━━━━━━━━━━━━\n"
            leaderboard_text += f"📍 <b>Ваша позиция:</b> {current_position}\n"
            leaderboard_text += f"💰 <b>Ваше богатство:</b> {current_wealth:.2f} USD\n"
            if current_btc > 0:
                leaderboard_text += f"   💵 {current_balance:.2f} USD + ₿ {current_btc:.8f} BTC\n"
    
    return leaderboard_text


def format_leaderboard_hashrate(top_players, user_id, owner_id):
    if not top_players:
        return (
            "⚡ <b>Топ игроков по хешрейту</b>\n\n"
            "📊 Пока нет игроков в рейтинге.\n"
            "Установите оборудование, чтобы попасть в топ!"
        )
    
    leaderboard_text = "⚡ <b>Топ игроков по хешрейту</b>\n\n"
    
                     
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for idx, player in enumerate(top_players):
        position = idx + 1
        raw_username = player.get('username')
        if raw_username:
            display_name = raw_username if len(raw_username) <= 20 else raw_username[:17] + "..."
            username_display = f'<a href="https://t.me/{raw_username}">{display_name}</a>'
        else:
            display_name = f"ID:{player['user_id']}"
            username_display = f'<a href="tg://user?id={player["user_id"]}">{display_name}</a>'
        hashrate = player.get('total_hashrate', 0) or 0
        
                                   
        if position <= 10:
            medal = medals[idx]
        else:
            medal = f"{position}."
        
        leaderboard_text += (
            f"{medal} <b>{username_display}</b>\n"
            f"   ⚡ {hashrate:.2f} H/s\n\n"
        )
    
                                        
    current_user = db.get_user(user_id)
    if current_user:
        current_hashrate = current_user.get('total_hashrate', 0) or 0
        
                                         
        current_position = None
        for idx, player in enumerate(top_players):
            if player['user_id'] == user_id:
                current_position = idx + 1
                break
        
        if current_position is None:
                                                           
            current_position = db.get_user_hashrate_position(user_id)
        
        if current_position and current_hashrate > 0:
            leaderboard_text += f"━━━━━━━━━━━━━━━━\n"
            leaderboard_text += f"📍 <b>Ваша позиция: {current_position}</b>\n"
            leaderboard_text += f"⚡ Ваш хешрейт: {current_hashrate:.2f} H/s"
    
    return leaderboard_text


def format_leaderboard_bitcoin(top_players, user_id, owner_id):
    if not top_players:
        return (
            "₿ <b>Топ держателей Bitcoin</b>\n\n"
            "📊 Пока нет игроков в рейтинге.\n"
            "Начните майнить, чтобы попасть в топ!"
        )
    
    leaderboard_text = "₿ <b>Топ 10 держателей Bitcoin</b>\n"
    leaderboard_text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    top_clan = db.get_top_clan_by_treasury()
    if top_clan:
        clan_name = html.escape(str(top_clan.get("name") or ""))
        clan_treasury = float(top_clan.get("treasury_usd") or 0)
        leader_id = int(top_clan.get("leader_id") or 0)
        leader_username = top_clan.get("leader_username")
        leader_link = _format_user_link(leader_id, str(leader_username) if leader_username else None)
        leaderboard_text += "🏴 <b>Самый богатый клан по казне</b>\n"
        leaderboard_text += f"🥇 <b>{clan_name}</b> — {clan_treasury:.2f} USD\n"
        leaderboard_text += f"👑 <b>Глава:</b> {leader_link}\n"
        leaderboard_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
                     
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for idx, player in enumerate(top_players):
        position = idx + 1
        username_display = _format_user_link(int(player.get("user_id") or 0), player.get("username"))
        bitcoin_balance = player.get('bitcoin_balance', 0) or 0
        
                                   
        if position <= 10:
            medal = medals[idx]
        else:
            medal = f"{position}."
        
        leaderboard_text += f"{medal} <b>{username_display}</b>\n"
        leaderboard_text += f"   ₿ {bitcoin_balance:.8f} BTC\n\n"
    
                                                       
    current_user = db.get_user(user_id)
    if current_user:
        current_btc = current_user.get('bitcoin_balance', 0) or 0
        
                                         
        current_position = None
        for idx, player in enumerate(top_players):
            if player['user_id'] == user_id:
                current_position = idx + 1
                break
        
        if current_position is None:
                                                           
            current_position = db.get_user_bitcoin_position(user_id)
        
        if current_position:
            leaderboard_text += "━━━━━━━━━━━━━━━━━━━━\n"
            leaderboard_text += f"📍 <b>Ваша позиция:</b> {current_position}\n"
            leaderboard_text += f"₿ <b>Ваш баланс:</b> {current_btc:.8f} BTC"
    
    return leaderboard_text


@router.message(Command("leaders"))
@router.message(F.text.startswith("/leaders"))
async def leaders_command(message: Message):
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

    top_players = db.get_top_players_by_bitcoin(limit=10)
    leaderboard_text = format_leaderboard_bitcoin(top_players, user_id, user_id)

    leaders_file_id = (db.get_setting("ui_image_leaders", "") or "").strip()
    await render_ui_from_message(
        message=message,
        owner_id=user_id,
        text=leaderboard_text,
        reply_markup=get_leaderboard_keyboard("bitcoin", user_id),
        parse_mode="HTML",
        disable_web_page_preview=True,
        prefer_reply_in_groups=True,
        ui_key="leaders",
        photo=(leaders_file_id if leaders_file_id else ""),
    )


@router.callback_query(F.data.startswith("main_leaderboard_"))
@router.callback_query(F.data.startswith("leaderboard_wealth_"))
async def leaderboard_wealth_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                                
    try:
        if callback.data.startswith("main_leaderboard_"):
            owner_id = int(callback.data.replace("main_leaderboard_", ""))
        else:
            owner_id = int(callback.data.replace("leaderboard_wealth_", ""))
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

    if callback.message is None or callback.message.chat is None:
        return

    chat_id = int(callback.message.chat.id)
    message_id = int(callback.message.message_id)
    current_key = (get_ui_key_for_message(chat_id, int(owner_id), message_id) or "").strip().lower()

    if current_key == "menu":
        target_key = "menu"
        photo_key = (db.get_setting("ui_image_menu", "") or "").strip()
        back_to_menu = True
    else:
        target_key = "leaders"
        photo_key = (db.get_setting("ui_image_leaders", "") or "").strip()
        back_to_menu = False

    set_ui_key_for_message(chat_id, int(owner_id), message_id, target_key)
    top_players = db.get_top_players_by_bitcoin(limit=10)
    leaderboard_text = format_leaderboard_bitcoin(top_players, user_id, owner_id)

    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=leaderboard_text,
        reply_markup=get_leaderboard_keyboard("bitcoin", owner_id, back_to_menu=back_to_menu),
        parse_mode="HTML",
        disable_web_page_preview=True,
        ui_key=target_key,
        photo=(photo_key if photo_key else ""),
    )


@router.callback_query(F.data.startswith("leaderboard_hashrate_"))
async def leaderboard_hashrate_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                                
    try:
        owner_id = int(callback.data.replace("leaderboard_hashrate_", ""))
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

    if callback.message is None or callback.message.chat is None:
        return

    chat_id = int(callback.message.chat.id)
    message_id = int(callback.message.message_id)
    current_key = (get_ui_key_for_message(chat_id, int(owner_id), message_id) or "").strip().lower()

    if current_key == "menu":
        target_key = "menu"
        photo_key = (db.get_setting("ui_image_menu", "") or "").strip()
        back_to_menu = True
    else:
        target_key = "leaders"
        photo_key = (db.get_setting("ui_image_leaders", "") or "").strip()
        back_to_menu = False

    set_ui_key_for_message(chat_id, int(owner_id), message_id, target_key)
    top_players = db.get_top_players_by_bitcoin(limit=10)
    leaderboard_text = format_leaderboard_bitcoin(top_players, user_id, owner_id)

    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=leaderboard_text,
        reply_markup=get_leaderboard_keyboard("bitcoin", owner_id, back_to_menu=back_to_menu),
        parse_mode="HTML",
        disable_web_page_preview=True,
        ui_key=target_key,
        photo=(photo_key if photo_key else ""),
    )


@router.callback_query(F.data.startswith("leaderboard_bitcoin_"))
async def leaderboard_bitcoin_handler(callback: CallbackQuery):
    save_chat_from_callback(callback)
                                                
    try:
        owner_id = int(callback.data.replace("leaderboard_bitcoin_", ""))
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

    if callback.message is None or callback.message.chat is None:
        return

    chat_id = int(callback.message.chat.id)
    message_id = int(callback.message.message_id)
    current_key = (get_ui_key_for_message(chat_id, int(owner_id), message_id) or "").strip().lower()

    if current_key == "menu":
        target_key = "menu"
        photo_key = (db.get_setting("ui_image_menu", "") or "").strip()
        back_to_menu = True
    else:
        target_key = "leaders"
        photo_key = (db.get_setting("ui_image_leaders", "") or "").strip()
        back_to_menu = False

    set_ui_key_for_message(chat_id, int(owner_id), message_id, target_key)
                                          
    top_players = db.get_top_players_by_bitcoin(limit=10)
    leaderboard_text = format_leaderboard_bitcoin(top_players, user_id, owner_id)

    await render_ui_from_callback(
        callback=callback,
        owner_id=owner_id,
        text=leaderboard_text,
        reply_markup=get_leaderboard_keyboard("bitcoin", owner_id, back_to_menu=back_to_menu),
        parse_mode="HTML",
        disable_web_page_preview=True,
        ui_key=target_key,
        photo=(photo_key if photo_key else ""),
    )

