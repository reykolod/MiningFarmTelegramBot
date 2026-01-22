from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from models import SHOP_CATEGORIES, CATEGORY_NAMES, SHOP_ITEMS, get_item_price_usd


def get_mining_farm_keyboard(owner_id: int, mining_enabled: bool = False) -> InlineKeyboardMarkup:
    start_button_text = "⏸️ Стоп" if mining_enabled else "▶️ Старт"
    start_callback = f"toggle_mining_{owner_id}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=start_button_text, callback_data=start_callback),
            InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_mining_{owner_id}")
        ],
        [
            InlineKeyboardButton(text="🛒 Магазин", callback_data=f"main_shop_{owner_id}"),
            InlineKeyboardButton(text="📦 Инвентарь", callback_data=f"main_inventory_{owner_id}")
        ],
        [
            InlineKeyboardButton(text="⚙️ Оборудование", callback_data=f"main_equipment_{owner_id}"),
            InlineKeyboardButton(text="💰 Кошелек", callback_data=f"main_wallet_{owner_id}")
        ],
        [
            InlineKeyboardButton(text="👤 Профиль", callback_data=f"main_profile_{owner_id}"),
            InlineKeyboardButton(text="☰ Меню", callback_data=f"main_menu_{owner_id}")
        ]
    ])
    return keyboard


def get_main_menu_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏆 Топ игроков", callback_data=f"main_leaderboard_{owner_id}"),
                InlineKeyboardButton(text="📚 Wiki", callback_data=f"main_wiki_{owner_id}"),
            ],
            [
                InlineKeyboardButton(text="🏴 Кланы", callback_data=f"main_clans_{owner_id}"),
                InlineKeyboardButton(text="ℹ️ Инфо", callback_data=f"main_info_{owner_id}"),
            ],
            [InlineKeyboardButton(text="ℹ️ Помощь", callback_data=f"main_help_{owner_id}")],
            [InlineKeyboardButton(text="🔙 Назад к ферме", callback_data=f"back_to_farm_{owner_id}")],
        ]
    )
    return keyboard




def get_shop_categories_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    back_callback = f"back_to_farm_{owner_id}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=CATEGORY_NAMES['rigs'], callback_data=f"shop_category_rigs_{owner_id}")],
        [InlineKeyboardButton(text=CATEGORY_NAMES['asic_rigs'], callback_data=f"shop_category_asic_rigs_{owner_id}")],
        [InlineKeyboardButton(text=CATEGORY_NAMES['gpu'], callback_data=f"shop_category_gpu_{owner_id}")],
        [InlineKeyboardButton(text=CATEGORY_NAMES['asic'], callback_data=f"shop_category_asic_{owner_id}")],
        [InlineKeyboardButton(text=CATEGORY_NAMES['cooling'], callback_data=f"shop_category_cooling_{owner_id}")],
        [InlineKeyboardButton(text=CATEGORY_NAMES['psu'], callback_data=f"shop_category_psu_{owner_id}")],
        [InlineKeyboardButton(text=CATEGORY_NAMES['consumables'], callback_data=f"shop_category_consumables_{owner_id}")],
        [InlineKeyboardButton(text="🔙 Назад к ферме", callback_data=back_callback)]
    ])
    return keyboard


def get_category_items_keyboard(category: str, owner_id: int) -> InlineKeyboardMarkup:
    item_ids = SHOP_CATEGORIES.get(category, [])
    keyboard_buttons = []
    
    for item_id in item_ids:
        item = SHOP_ITEMS[item_id]
        price_usd = get_item_price_usd(item_id)
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{item.name} - {int(price_usd)} USD",
                callback_data=f"shop_item_{item_id}_{owner_id}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад в магазин", callback_data=f"back_to_shop_{owner_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


def get_item_detail_keyboard(item_id: str, owner_id: int, category: str = None) -> InlineKeyboardMarkup:
    if category:
        back_callback = f"shop_category_{category}_{owner_id}"
    else:
                                     
        for cat, items in SHOP_CATEGORIES.items():
            if item_id in items:
                back_callback = f"shop_category_{cat}_{owner_id}"
                break
        else:
            back_callback = f"back_to_shop_{owner_id}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить", callback_data=f"buy_item_{item_id}_{owner_id}")],
        [InlineKeyboardButton(text="🔙 Назад к категории", callback_data=back_callback)]
    ])
    return keyboard


def get_inventory_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к ферме", callback_data=f"back_to_farm_{owner_id}")]
    ])
    return keyboard


def get_equipment_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к ферме", callback_data=f"back_to_farm_{owner_id}")]
    ])
    return keyboard


def get_wallet_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    back_callback = f"back_to_farm_{owner_id}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Собрать BTC", callback_data=f"collect_bitcoin_{owner_id}")],
        [InlineKeyboardButton(text="💱 Обменять BTC → USD", callback_data=f"exchange_bitcoin_{owner_id}")],
        [InlineKeyboardButton(text="💵 Купить BTC за USD", callback_data=f"buy_bitcoin_{owner_id}")],
        [
            InlineKeyboardButton(
                text="🏦 В банк (USD)",
                callback_data=f"wallet_deposit_usd_{owner_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="🏦 В банк (BTC)",
                callback_data=f"wallet_deposit_btc_{owner_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="🏧 Снять с банка (USD)",
                callback_data=f"wallet_withdraw_usd_{owner_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="🏧 Снять с банка (BTC)",
                callback_data=f"wallet_withdraw_btc_{owner_id}",
            )
        ],
        [InlineKeyboardButton(text="🔙 Назад к ферме", callback_data=back_callback)]
    ])
    return keyboard


def get_back_to_farm_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к ферме", callback_data=f"back_to_farm_{owner_id}")]
    ])
    return keyboard


def get_inventory_item_keyboard(item_id: str, quantity: int, owner_id: int) -> InlineKeyboardMarkup:
    buttons = []

    item = SHOP_ITEMS.get(item_id)

    if item is None or item.item_type != "consumable":
        buttons.append([InlineKeyboardButton(text="⚙️ Установить", callback_data=f"install_item_{item_id}_{owner_id}")])

    if item is not None and item.item_type == "consumable":
        buttons.append(
            [
                InlineKeyboardButton(
                    text="🧹 Использовать",
                    callback_data=f"use_consumable_{item_id}_{owner_id}",
                )
            ]
        )
    
                                            
    buttons.append([InlineKeyboardButton(text="💸 Продать барыге", callback_data=f"fence_offer_{item_id}_{owner_id}")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад в инвентарь", callback_data=f"main_inventory_{owner_id}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


def get_fence_offer_keyboard(item_id: str, owner_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Продать", callback_data=f"sell_confirm_{item_id}_{owner_id}")],
        [InlineKeyboardButton(text="❌ Отказаться", callback_data=f"inventory_item_{item_id}_{owner_id}")],
        [InlineKeyboardButton(text="🔙 Назад к ферме", callback_data=f"back_to_farm_{owner_id}")],
    ])
    return keyboard


def get_equipment_item_keyboard(item_id: str, quantity: int, owner_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Снять с фермы", callback_data=f"uninstall_item_{item_id}_{owner_id}")],
        [InlineKeyboardButton(text="🔙 Назад к оборудованию", callback_data=f"main_equipment_{owner_id}")]
    ])
    return keyboard


def get_leaderboard_keyboard(leaderboard_type: str, owner_id: int, back_to_menu: bool = False) -> InlineKeyboardMarkup:
    back_callback = f"main_menu_{owner_id}" if back_to_menu else f"back_to_farm_{owner_id}"

    buttons = []

    buttons.append([InlineKeyboardButton(text="₿ Топ держателей BTC", callback_data=f"leaderboard_bitcoin_{owner_id}")])

    buttons.append([InlineKeyboardButton(text=("🔙 Назад в меню" if back_to_menu else "🔙 Назад к ферме"), callback_data=back_callback)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_wiki_categories_keyboard(owner_id: int, back_to_menu: bool = False) -> InlineKeyboardMarkup:
    rows = []

                                                                     
    for key in ["rigs", "asic_rigs", "gpu", "asic", "cooling", "psu"]:
        if key in CATEGORY_NAMES:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=CATEGORY_NAMES[key],
                        callback_data=f"wiki_cat_{key}_{owner_id}",
                    )
                ]
            )

    if back_to_menu:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔙 Назад в меню",
                    callback_data=f"main_menu_{owner_id}",
                )
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔙 Назад к ферме",
                    callback_data=f"back_to_farm_{owner_id}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_clans_keyboard(owner_id: int, has_clan: bool, is_leader: bool = False) -> InlineKeyboardMarkup:
    rows = []

    if has_clan:
        rows.append(
            [
                InlineKeyboardButton(text="💰 Казна", callback_data=f"clans_treasury_{owner_id}"),
            ]
        )

        rows.append(
            [
                InlineKeyboardButton(text="🛒 Магазин клана", callback_data=f"clans_shop_{owner_id}"),
                InlineKeyboardButton(text="🧾 Лог", callback_data=f"clans_events_{owner_id}"),
            ]
        )

        if is_leader:
            rows.append(
                [
                    InlineKeyboardButton(text="👥 Участники", callback_data=f"clans_members_{owner_id}"),
                    InlineKeyboardButton(text="🧨 Распустить", callback_data=f"clans_disband_{owner_id}"),
                ]
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(text="👥 Участники", callback_data=f"clans_members_{owner_id}"),
                    InlineKeyboardButton(text="🚪 Выйти", callback_data=f"clans_leave_{owner_id}"),
                ]
            )

        if is_leader:
            rows.append(
                [
                    InlineKeyboardButton(text="📨 Пригласить", callback_data=f"clans_invite_hint_{owner_id}"),
                ]
            )
    else:
        rows.append(
            [
                InlineKeyboardButton(text="➕ Создать клан", callback_data=f"clans_create_hint_{owner_id}"),
            ]
        )

    rows.append([InlineKeyboardButton(text="🔙 Назад в меню", callback_data=f"main_menu_{owner_id}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад к ферме", callback_data=f"back_to_farm_{owner_id}")])

    return InlineKeyboardMarkup(inline_keyboard=rows)
