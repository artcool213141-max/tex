import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from supabase import create_client

# Твои данные напрямую
BOT_TOKEN = "8902977298:AAFXq-RNoSx7qZiUtxwKBPhlkh5La3iQ_fs"
SUPABASE_URL = "https://xjucalpaoqlrtmofmden.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhqdWNhbHBhb3FscnRtb2ZtZGVuI","cm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjQ0MjM4NywiZXhwIjoyMDkyMDE4Mzg3fQ.CCo4AgdSwWbbUSAL8W1OCbAtTChaL5zSN4Q6Pd_8RN0"
# Убедись, что ключ вставлен целиком без разрывов (здесь он полностью из твоего сообщения):
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhqdWNhbHBhb3FscnRtb2ZtZGVuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjQ0MjM4NywiZXhwIjoyMDkyMDE4Mzg3fQ.CCo4AgdSwWbbUSAL8W1OCbAtTChaL5zSN4Q6Pd_8RN0"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Список твоих таблиц
TABLES = [
    "users", "promo_codes", "orders", "ambassador_codes", 
    "ambassador_activations", "ambassador_deposits"
]

class AdminStates(StatesGroup):
    waiting_for_search = State()

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"📁 {table}", callback_data=f"table_{table}")]
            for table in TABLES
        ]
    )
    await message.answer("🗄 **Панель управления Supabase**\n\nВыбери таблицу для управления:", parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("table_"))
async def show_table(callback: CallbackQuery, state: FSMContext):
    table_name = callback.data.split("_")[1]
    await state.update_data(current_table=table_name)
    
    try:
        res = supabase.table(table_name).select("*").limit(5).execute()
        rows = res.data
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка запроса к базе: {e}")
        return

    text = f"📂 Таблица: **{table_name}**\nПоследние записи (до 5):\n\n"
    if not rows:
        text += "*(пусто)*"
    for r in rows:
        text += f"<code>{r}</code>\n\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск по таблице", callback_data=f"search_{table_name}")],
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_tables")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("search_"))
async def ask_search_query(callback: CallbackQuery, state: FSMContext):
    table_name = callback.data.split("_")[1]
    await state.set_state(AdminStates.waiting_for_search)
    await state.update_data(current_table=table_name)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"table_{table_name}")]
    ])
    
    await callback.message.edit_text(
        f"🔍 Введи текст, ID или промокод для поиска в таблице **{table_name}**:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.message(AdminStates.waiting_for_search)
async def process_search(message: Message, state: FSMContext):
    data = await state.get_data()
    table_name = data.get("current_table")
    query_text = message.text.strip()

    try:
        res = supabase.table(table_name).select("*").limit(20).execute()
        rows = [r for r in res.data if any(query_text.lower() in str(v).lower() for v in r.values())]
    except Exception as e:
        await message.answer(f"❌ Ошибка поиска: {e}")
        return

    if not rows:
        text = f"Ничего не найдено по запросу: *{query_text}*"
    else:
        text = f"🔍 Найдено совпадений: {len(rows)}\n\n"
        for r in rows:
            text += f"<code>{r}</code>\n\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К таблице", callback_data=f"table_{table_name}")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await state.clear()

@dp.callback_query(F.data == "back_to_tables")
async def back_to_tables(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"📁 {table}", callback_data=f"table_{table}")]
            for table in TABLES
        ]
    )
    await callback.message.edit_text("🗄 **Панель управления Supabase**\n\nВыбери таблицу:", parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
