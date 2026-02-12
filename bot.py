import json
import random
import logging
import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- НАСТРОЙКИ ---
TOKEN = "8562059881:AAGZk5nCQIvR8eD0yIGPPsRU13amsg37sjw"

logging.basicConfig(level=logging.INFO)

class QuizStates(StatesGroup):
    choosing_lang = State()
    in_progress = State()

# --- ЗАГРУЗКА ДАННЫХ ---
def load_questions():
    data = {"ru": [], "en": []}
    for lang in ["ru", "en"]:
        filename = f'questions_{lang}.json'
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                data[lang] = json.load(f)
        else:
            logging.error(f"Файл {filename} не найден!")
    return data

QUESTIONS = load_questions()

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="Русский 🇷🇺", callback_data="lang_ru"),
        types.InlineKeyboardButton(text="English 🇬🇧", callback_data="lang_en")
    )
    await message.answer("Выберите язык теста / Choose language:", reply_markup=builder.as_markup())
    await state.set_state(QuizStates.choosing_lang)

@dp.callback_query(F.data.startswith("lang_"))
async def select_lang(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    if not QUESTIONS[lang]:
        await callback.answer("Ошибка: вопросы не загружены.", show_alert=True)
        return

    # Выбираем 20 случайных вопросов
    pool = random.sample(QUESTIONS[lang], min(len(QUESTIONS[lang]), 20))
    
    await state.update_data(
        lang=lang,
        questions=pool,
        current_idx=0,
        score=0
    )
    await callback.answer()
    await send_question(callback.message, state)

async def send_question(message: types.Message, state: FSMContext):
    data = await state.get_data()
    q_idx = data['current_idx']
    questions = data['questions']
    lang = data['lang']

    if q_idx < len(questions):
        question = questions[q_idx]
        
        # Перемешиваем варианты
        options = list(question['options'])
        random.shuffle(options)
        
        # Сохраняем перемешанные варианты, чтобы знать, под какой буквой какой ответ
        await state.update_data(current_options=options)

        # Формируем текст вопроса и список вариантов A, B, C...
        labels = ["A", "B", "C", "D"]
        options_text = ""
        builder = InlineKeyboardBuilder()
        
        for i, opt in enumerate(options):
            label = labels[i]
            options_text += f"**{label})** {opt}\n"
            # В кнопку кладем только индекс '0', '1'...
            builder.add(types.InlineKeyboardButton(text=label, callback_data=f"ans_{i}"))
        
        builder.adjust(2) # Кнопки по 2 в ряд (A B / C D)

        header = "Вопрос" if lang == "ru" else "Question"
        text = f"❓ **{header} {q_idx + 1}/{len(questions)}**\n\n{question['text']}\n\n{options_text}"
        
        await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        await state.set_state(QuizStates.in_progress)
    else:
        # Финал
        score, total = data['score'], len(questions)
        msg = f"🏆 Результат: {score}/{total}" if lang == "ru" else f"🏆 Result: {score}/{total}"
        await message.edit_text(msg)
        await state.clear()

@dp.callback_query(F.data.startswith("ans_"), QuizStates.in_progress)
async def handle_answer(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang, q_idx = data['lang'], data['current_idx']
    question = data['questions'][q_idx]
    
    # Получаем выбранный вариант через индекс
    ans_idx = int(callback.data.split("_")[1])
    user_ans = data['current_options'][ans_idx]
    
    is_correct = user_ans == question['correct']
    
    if is_correct:
        await state.update_data(score=data['score'] + 1)
        res_text = "✅ Верно!" if lang == "ru" else "✅ Correct!"
    else:
        res_text = f"❌ Ошибка!\nОжидалось: {question['correct']}" if lang == "ru" else f"❌ Wrong!\nExpected: {question['correct']}"
    
    note_text = f"\n\n📖 {question['note']}" if question.get('note') else ""
    
    builder = InlineKeyboardBuilder()
    btn_text = "Далее ➡️" if lang == "ru" else "Next ➡️"
    builder.add(types.InlineKeyboardButton(text=btn_text, callback_data="next_q"))

    await callback.message.edit_text(f"{res_text}{note_text}", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "next_q")
async def next_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.update_data(current_idx=data['current_idx'] + 1)
    await send_question(callback.message, state)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())