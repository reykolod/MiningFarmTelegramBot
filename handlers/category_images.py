from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from config import ADMIN_ID
from database import db
from models import CATEGORY_NAMES
import os

router = Router()

_ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


UI_SCREENS: dict[str, str] = {
    "mining": "⛏️ Управление фермой",
    "farm": "⛏️ Управление фермой",
    "menu": "☰ Главное меню",
    "shop": "🛒 Магазин",
    "inventory": "📦 Инвентарь",
    "equipment": "⚙️ Оборудование",
    "wallet": "💰 Кошелек",
    "profile": "👤 Профиль",
    "wiki": "📚 Wiki",
    "info": "ℹ️ Информация",
    "leaders": "🏆 Топ игроков",
    "clans": "🏴 Кланы",
}


@router.message(Command("set_cat_image"))
@router.message(F.text.startswith("/set_cat_image"))
async def cmd_set_cat_image(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    command_text = message.text or ""
    parts = command_text.split()
    if len(parts) < 2:
        categories = ", ".join(sorted(CATEGORY_NAMES.keys()))
        await message.answer(
            "❌ Неверный формат команды!\n\n"
            "Используйте: /set_cat_image <category> <filename>\n\n"
            "Файл должен лежать в папке <code>ui_media</code>.\n"
            "Пример: /set_cat_image gpu shop_gpu.jpg\n\n"
            f"Доступные категории: {categories}"
        )
        return

    category = (parts[1] or "").strip()
    if category not in CATEGORY_NAMES:
        categories = ", ".join(sorted(CATEGORY_NAMES.keys()))
        await message.answer(f"❌ Неизвестная категория. Доступные: {categories}")
        return

    filename = (parts[2] if len(parts) >= 3 else "")
    filename = (filename or "").strip()
    if not filename:
        await message.answer("❌ Не указано имя файла. Пример: /set_cat_image gpu shop_gpu.jpg")
        return

    ext = os.path.splitext(filename)[1].lower()
    if ext and ext not in _ALLOWED_IMAGE_EXTS:
        await message.answer(
            "❌ Неверное расширение файла. Разрешено: .jpg, .jpeg, .png, .webp",
        )
        return

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui_media"))
    rel = filename.lstrip("/\\")
    full = os.path.abspath(os.path.join(base_dir, rel))
    if not (full == base_dir or full.startswith(base_dir + os.sep)) or not os.path.isfile(full):
        await message.answer(
            "❌ Файл не найден. Он должен существовать в папке <code>ui_media</code>.",
            parse_mode="HTML",
        )
        return

    db.set_setting(f"cat_image_{category}", rel)
    await message.answer(
        f"✅ Картинка для категории <b>{CATEGORY_NAMES.get(category, category)}</b> сохранена.\n"
        f"Ключ: <code>cat_image_{category}</code>",
        parse_mode="HTML",
    )


@router.message(Command("clear_cat_image"))
@router.message(F.text.startswith("/clear_cat_image"))
async def cmd_clear_cat_image(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    command_text = message.text or ""
    parts = command_text.split()
    if len(parts) < 2:
        categories = ", ".join(sorted(CATEGORY_NAMES.keys()))
        await message.answer(
            "❌ Неверный формат команды!\n\n"
            "Используйте: /clear_cat_image <category>\n"
            "Пример: /clear_cat_image gpu\n\n"
            f"Доступные категории: {categories}"
        )
        return

    category = (parts[1] or "").strip()
    if category not in CATEGORY_NAMES:
        categories = ", ".join(sorted(CATEGORY_NAMES.keys()))
        await message.answer(f"❌ Неизвестная категория. Доступные: {categories}")
        return

    db.set_setting(f"cat_image_{category}", "")
    await message.answer(
        f"✅ Картинка для категории <b>{CATEGORY_NAMES.get(category, category)}</b> очищена.",
        parse_mode="HTML",
    )


@router.message(Command("set_ui_image"))
@router.message(F.text.startswith("/set_ui_image"))
async def cmd_set_ui_image(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    command_text = message.text or ""
    parts = command_text.split()
    if len(parts) < 2:
        screens = ", ".join(sorted(UI_SCREENS.keys()))
        await message.answer(
            "❌ Неверный формат команды!\n\n"
            "Используйте: /set_ui_image <screen> <filename>\n\n"
            "Файл должен лежать в папке <code>ui_media</code>.\n"
            "Пример: /set_ui_image menu menu.jpg\n\n"
            f"Доступные экраны: {screens}"
        )
        return

    screen = (parts[1] or "").strip()
    if screen not in UI_SCREENS:
        screens = ", ".join(sorted(UI_SCREENS.keys()))
        await message.answer(f"❌ Неизвестный экран. Доступные: {screens}")
        return

    filename = (parts[2] if len(parts) >= 3 else "")
    filename = (filename or "").strip()
    if not filename:
        await message.answer("❌ Не указано имя файла. Пример: /set_ui_image menu menu.jpg")
        return

    ext = os.path.splitext(filename)[1].lower()
    if ext and ext not in _ALLOWED_IMAGE_EXTS:
        await message.answer(
            "❌ Неверное расширение файла. Разрешено: .jpg, .jpeg, .png, .webp",
        )
        return

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui_media"))
    rel = filename.lstrip("/\\")
    full = os.path.abspath(os.path.join(base_dir, rel))
    if not (full == base_dir or full.startswith(base_dir + os.sep)) or not os.path.isfile(full):
        await message.answer(
            "❌ Файл не найден. Он должен существовать в папке <code>ui_media</code>.",
            parse_mode="HTML",
        )
        return

    db.set_setting(f"ui_image_{screen}", rel)
    await message.answer(
        f"✅ Картинка для экрана <b>{UI_SCREENS.get(screen, screen)}</b> сохранена.\n"
        f"Ключ: <code>ui_image_{screen}</code>",
        parse_mode="HTML",
    )


@router.message(Command("clear_ui_image"))
@router.message(F.text.startswith("/clear_ui_image"))
async def cmd_clear_ui_image(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    command_text = message.text or ""
    parts = command_text.split()
    if len(parts) < 2:
        screens = ", ".join(sorted(UI_SCREENS.keys()))
        await message.answer(
            "❌ Неверный формат команды!\n\n"
            "Используйте: /clear_ui_image <screen>\n"
            "Пример: /clear_ui_image shop\n\n"
            f"Доступные экраны: {screens}"
        )
        return

    screen = (parts[1] or "").strip()
    if screen not in UI_SCREENS:
        screens = ", ".join(sorted(UI_SCREENS.keys()))
        await message.answer(f"❌ Неизвестный экран. Доступные: {screens}")
        return

    db.set_setting(f"ui_image_{screen}", "")
    await message.answer(
        f"✅ Картинка для экрана <b>{UI_SCREENS.get(screen, screen)}</b> очищена.",
        parse_mode="HTML",
    )


@router.message(Command("clear_all_ui_images"))
@router.message(F.text.startswith("/clear_all_ui_images"))
async def cmd_clear_all_ui_images(message: Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    cleared: list[str] = []
    for screen in sorted(UI_SCREENS.keys()):
        db.set_setting(f"ui_image_{screen}", "")
        cleared.append(str(screen))

    await message.answer(
        "✅ Очищены все картинки UI-меню.\n"
        f"Экраны: <code>{', '.join(cleared)}</code>",
        parse_mode="HTML",
    )
