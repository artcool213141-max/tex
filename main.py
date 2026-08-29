import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from supabase import create_client

# Твои доступы
BOT_TOKEN = "8902977298:AAFXq-RNoSx7qZiUtxwKBPhlkh5La3iQ_fs"
SUPABASE_URL = "https://xjucalpaoqlrtmofmden.supabase.co"
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
    waiting_for_field_value = State()

# --- 1. ГЛАВНОЕ МЕНЮ (СПИСОК ТАБЛИЦ) ---
@dp.message(Command("start"))
@dp.callback_query(F.data == "back_to_tables")
async def cmd_start(update, state: FSMContext):
    await state.clear()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"📁 {table}", callback_data=f"table_{table}")]
            for table in TABLES
        ]
    )
    text = "🗄 **Панель управления Supabase**\n\nВыбери таблицу:"
    if isinstance(update, Message):
        await update.answer(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
        await update.answer()

# --- 2. СПИСОК ЗАПИСЕЙ КНОПКАМИ ПО ВЫБОРУ ТАБЛИЦЫ ---
@dp.callback_query(F.data.startswith("table_") & ~F.data.contains("row"))
async def show_table_records(callback: CallbackQuery, state: FSMContext):
    table_name = callback.data.split("_")[1]
    await state.update_data(current_table=table_name)
    
    try:
        # Пытаемся взять последние 10 записей
        res = supabase.table(table_name).select("*").limit(10).execute()
        rows = res.data
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка запроса: {e}")
        return

    if not rows:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Поиск", callback_data=f"search_{table_name}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_tables")]
        ])
        await callback.message.edit_text(f"📂 Таблица: **{table_name}**\n\n*(Пусто)*", parse_mode="Markdown", reply_markup=keyboard)
        await callback.answer()
        return

    # Определяем ключевое поле для идентификации строки (user_id, id или первое попавшееся)
    first_row = rows[0]
    id_key = "user_id" if "user_id" in first_row else ("id" in first_row and "id" or list(first_row.keys())[0])

    buttons = []
    for r in rows:
        row_id = r.get(id_key, "запись")
        buttons.append([InlineKeyboardButton(text=f"🆔 {row_id}", callback_data=f"row_{table_name}_{row_id}")])

    # Добавляем кнопки поиска и возврата
    buttons.append([InlineKeyboardButton(text="🔍 Поиск по таблице", callback_data=f"search_{table_name}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад к таблицам", callback_data="back_to_tables")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(f"📂 Таблица: **{table_name}**\nВыбери запись для просмотра:", parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()

# --- 3. ПОИСК ПО ТАБЛИЦЕ ---
@dp.callback_query(F.data.startswith("search_"))
async def ask_search_query(callback: CallbackQuery, state: FSMContext):
    table_name = callback.data.split("_")[1]
    await state.set_state(AdminStates.waiting_for_search)
    await state.update_data(current_table=table_name)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"table_{table_name}")]
    ])
    await callback.message.edit_text(f"🔍 Введи ID или текст для поиска в **{table_name}**:", parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()

@dp.message(AdminStates.waiting_for_search)
async def process_search(message: Message, state: FSMContext):
    data = await state.get_data()
    table_name = data.get("current_table")
    query_text = message.text.strip()

    try:
        res = supabase.table(table_name).select("*").limit(15).execute()
        rows = [r for r in res.data if any(query_text.lower() in str(v).lower() for v in r.values())]
    except Exception as e:
        await message.answer(f"❌ Ошибка поиска: {e}")
        return

    if not rows:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К таблице", callback_data=f"table_{table_name}")]
        ])
        await message.answer(f"Ничего не найдено по запросу: *{query_text}*", parse_mode="Markdown", reply_markup=keyboard)
        await state.clear()
        return

    first_row = rows[0]
    id_key = "user_id" if "user_id" in first_row else ("id" in first_row and "id" or list(first_row.keys())[0])

    buttons = []
    for r in rows:
        row_id = r.get(id_key, "запись")
        buttons.append([InlineKeyboardButton(text=f"🔍 Найдено: {row_id}", callback_data=f"row_{table_name}_{row_id}")])
    
    buttons.append([InlineKeyboardButton(text="⬅️ К таблице", callback_data=f"table_{table_name}")])

    await message.answer(f"🔍 Результаты поиска ({len(rows)}):", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.clear()

# --- 4. ПРОСМОТР КОНКРЕТНОЙ ЗАПИСИ И ЕЕ КОЛОНОК КНОПКАМИ ---
@dp.callback_query(F.data.startswith("row_"))
async def show_row_details(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    table_name = parts[1]
    row_id = "_".join(parts[2:]) # На случай если ID длинный или числовой

    await state.update_data(current_table=table_name, current_row_id=row_id)

    # Определяем название первичного ключа
    id_key = "user_id" if table_name == "users" else "id"
    
    try:
        # Пробуем найти по числовому ID или текстовому
        try:
            real_id = int(row_id)
        except ValueError:
            real_id = row_id

        res = supabase.table(table_name).select("*").eq(id_key, real_id).execute()
        if not res.data:
            # Если не нашли по id, попробуем поискать среди первых строк
            res = supabase.table(table_name).select("*").limit(20).execute()
            row_data = next((r for r in res.data if str(r.get(id_key)) == str(row_id)), None)
        else:
            row_data = res.data[0]
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка загрузки записи: {e}")
        return

    if not row_data:
        await callback.message.answer("❌ Запись не найдена в базе.")
        return

    await state.update_data(row_data=row_data)

    # Создаем кнопки для каждого поля (колоночки)
    buttons = []
    for field_name, value in row_data.items():
        # Обрезаем длинные значения для красоты на кнопке
        val_str = str(value)
        if len(val_str) > 20:
            val_str = val_str[:17] + "..."
        buttons.append([InlineKeyboardButton(text=f"✏️ {field_name}: {val_str}", callback_data=f"edit_{field_name}")])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад к списку", callback_data=f"table_{table_name}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        f"📝 Карточка записи в **{table_name}** (`{id_key}: {row_id}`)\nНажми на поле, чтобы изменить его значение:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await callback.answer()

# --- 5. РЕДАКТИРОВАНИЕ ПОЛЯ ---
@dp.callback_query(F.data.startswith("edit_"))
async def ask_new_field_value(callback: CallbackQuery, state: FSMContext):
    field_name = callback.data.replace("edit_", "", 1)
    await state.update_data(editing_field=field_name)
    await state.set_state(AdminStates.waiting_for_field_value)

    data = await state.get_data()
    table_name = data.get("current_table")
    row_id = data.get("current_row_id")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"row_{table_name}_{row_id}")]
    ])
    await callback.message.edit_text(
        f"✍️ Введи новое значение для поля **{field_name}**:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.message(AdminStates.waiting_for_field_value)
async def save_new_field_value(message: Message, state: FSMContext):
    data = await state.get_data()
    table_name = data.get("current_table")
    row_id = data.get("current_row_id")
    field_name = data.get("editing_field")
    new_value = message.text.strip()

    id_key = "user_id" if table_name == "users" else "id"
    try:
        try:
            real_id = int(row_id)
        except ValueError:
            real_id = row_id

        # Автоматический перевод чисел и булевых значений для корректности типов в базе
        parsed_value = new_value
        if new_value.lower() == "true":
            parsed_value = True
        elif new_value.lower() == "false":
            parsed_value = False
        else:
            try:
                if "." in new_value:
                    parsed_value = float(new_value)
                else:
                    parsed_value = int(new_value)
            except ValueError:
                pass

        # Обновляем в Supabase
        supabase.table(table_name).update({field_name: parsed_value}).eq(id_key, real_id).execute()
        
        await message.answer(f"✅ Успешно! Поле `{field_name}` обновлено на `{new_value}`.")
    except Exception as e:
        await message.answer(f"❌ Ошибка обновления в базе: {e}")

    await state.clear()

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
