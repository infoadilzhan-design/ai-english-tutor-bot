from __future__ import annotations
from gtts import gTTS
import os
import asyncio
import logging
import re
import tempfile
from pathlib import Path
from typing import Optional, Any

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    FSInputFile, 
    Message, 
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotenv import load_dotenv

# Internal module imports
from content_service import (
    generate_grammar_content,
    generate_quiz_content,
    generate_vocabulary_content,
    generate_podcast_script
)
from pdf_tools import (
    build_grammar_pdf, 
    build_quiz_pdf, 
    build_vocabulary_pdf
)

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing in .env file")

router = Router()

# FSM States
class TutorStates(StatesGroup):
    waiting_for_level = State()
    waiting_vocab_topic = State()
    waiting_vocab_count = State()
    waiting_grammar_topic = State()
    waiting_quiz_topic = State()
    waiting_quiz_count = State()
    waiting_podcast_topic = State()
    waiting_podcast_voice = State()
    waiting_podcast_length = State()

# --- KEYBOARDS ---

def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="Vocabulary 📘")
    kb.button(text="Grammar 📙")
    kb.button(text="Podcast 🎙")
    kb.button(text="Quiz ✅")
    kb.button(text="Change Level ⚙️")
    kb.adjust(2, 2, 1)
    return kb.as_markup(resize_keyboard=True)

def back_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="Main menu 🏠")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)

async def send_main_menu(target: Message, state: Optional[FSMContext] = None):
    """Resets the flow while preserving the user's English level."""
    if state is not None:
        data = await state.get_data()
        current_level = data.get("user_level", "A1")
        await state.clear()
        await state.update_data(user_level=current_level)
    await target.answer("Choose a section to start practicing:", reply_markup=main_menu())

# --- START & LEVEL SELECTION ---

@router.message(CommandStart())
@router.message(F.text == "Change Level ⚙️")
async def start_cmd(message: Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Beginner (A1)", callback_data="set_level_A1"),
         InlineKeyboardButton(text="Elementary (A2)", callback_data="set_level_A2")],
        [InlineKeyboardButton(text="Intermediate (B1)", callback_data="set_level_B1"),
         InlineKeyboardButton(text="Upper-Intermediate (B2)", callback_data="set_level_B2")],
    ])
    await state.set_state(TutorStates.waiting_for_level)
    await message.answer("Hello! Please select your English level:", reply_markup=kb)

@router.callback_query(TutorStates.waiting_for_level, F.data.startswith("set_level_"))
async def handle_level_selection(callback: CallbackQuery, state: FSMContext):
    level = callback.data.replace("set_level_", "")
    await state.update_data(user_level=level)
    await callback.answer(f"Level set to {level}")
    await callback.message.edit_text(f"✅ Your level is: <b>{level}</b>. What would you like to do?")
    await send_main_menu(callback.message)

@router.message(F.text == "Main menu 🏠")
async def back_to_home(message: Message, state: FSMContext):
    await send_main_menu(message, state)

# --- VOCABULARY SECTION ---

@router.message(F.text == "Vocabulary 📘")
async def vocab_start(message: Message, state: FSMContext):
    await state.set_state(TutorStates.waiting_vocab_topic)
    await message.answer("Enter a topic for your vocabulary lesson (e.g., Cooking, Travel):", reply_markup=back_menu())

@router.message(TutorStates.waiting_vocab_topic, F.text)
async def handle_vocab_topic(message: Message, state: FSMContext):
    # Safety check for navigation buttons
    if message.text in ["Main menu 🏠", "Change Level ⚙️"]:
        if message.text == "Change Level ⚙️": await start_cmd(message, state)
        else: await send_main_menu(message, state)
        return

    await state.update_data(topic=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="5 Words", callback_data="vcount_5"),
         InlineKeyboardButton(text="10 Words", callback_data="vcount_10")],
        [InlineKeyboardButton(text="20 Words", callback_data="vcount_20")]
    ])
    await state.set_state(TutorStates.waiting_vocab_count)
    await message.answer(f"Topic: {message.text}. How many words should I include?", reply_markup=kb)

@router.callback_query(TutorStates.waiting_vocab_count, F.data.startswith("vcount_"))
async def finalize_vocab(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    count = int(callback.data.replace("vcount_", ""))
    data = await state.get_data()
    topic = data.get("topic")
    level = data.get("user_level", "A1")

    await callback.message.edit_text(f"⏳ Generating {count} words for {level} level...")
    content = await generate_vocabulary_content(topic, count, level=level)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / f"vocab_{slugify(topic)}.pdf"
        build_vocabulary_pdf(content, pdf_path)
        await callback.message.answer_document(
            FSInputFile(pdf_path), 
            caption=f"📘 Vocabulary: {topic}\nLevel: {level}"
        )
    await send_main_menu(callback.message, state)

# --- GRAMMAR SECTION ---

@router.message(F.text == "Grammar 📙")
async def grammar_start(message: Message, state: FSMContext):
    await state.set_state(TutorStates.waiting_grammar_topic)
    await message.answer("Enter a Grammar topic (e.g., Present Continuous):", reply_markup=back_menu())

@router.message(TutorStates.waiting_grammar_topic, F.text)
async def handle_grammar(message: Message, state: FSMContext):
    if message.text in ["Main menu 🏠", "Change Level ⚙️"]:
        if message.text == "Change Level ⚙️": await start_cmd(message, state)
        else: await send_main_menu(message, state)
        return

    data = await state.get_data()
    level = data.get("user_level", "A1")
    topic = message.text.strip()

    await message.answer(f"⏳ Generating grammar guide for {topic}...")
    content = await generate_grammar_content(topic, level=level)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / f"grammar_{slugify(topic)}.pdf"
        build_grammar_pdf(content, pdf_path)
        await message.answer_document(FSInputFile(pdf_path), caption=f"Grammar PDF: {topic}")
    await send_main_menu(message, state)

# --- QUIZ SECTION ---

@router.message(F.text == "Quiz ✅")
async def quiz_start(message: Message, state: FSMContext):
    await state.set_state(TutorStates.waiting_quiz_topic)
    await message.answer("Topic for the Quiz (e.g., Adjectives, Food):", reply_markup=back_menu())

@router.message(TutorStates.waiting_quiz_topic, F.text)
async def handle_quiz_topic(message: Message, state: FSMContext):
    if message.text in ["Main menu 🏠", "Change Level ⚙️"]:
        if message.text == "Change Level ⚙️": await start_cmd(message, state)
        else: await send_main_menu(message, state)
        return
    await state.update_data(topic=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="5 Questions", callback_data="qcount_5"),
         InlineKeyboardButton(text="10 Questions", callback_data="qcount_10")]
    ])
    await state.set_state(TutorStates.waiting_quiz_count)
    await message.answer("How many questions?", reply_markup=kb)

@router.callback_query(TutorStates.waiting_quiz_count, F.data.startswith("qcount_"))
async def finalize_quiz(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    count = int(callback.data.replace("qcount_", ""))
    data = await state.get_data()
    topic = data.get("topic")
    level = data.get("user_level", "A1")

    await callback.message.edit_text(f"⏳ Preparing your {level} level quiz...")
    content = await generate_quiz_content(topic, count, level=level)
    questions = content.get("multiple_choice", [])
    
    if questions:
        for q in questions:
            options = q.get("options", [])
            correct_ans = q.get("answer", "")
            try:
                correct_id = options.index(correct_ans)
            except ValueError:
                correct_id = 0
            
            await callback.message.answer_poll(
                question=q.get("question")[:255],
                options=options,
                type="quiz",
                correct_option_id=correct_id,
                is_anonymous=False,
                explanation=q.get("explanation")[:200]
            )
            await asyncio.sleep(0.5)

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / f"quiz_{slugify(topic)}.pdf"
        build_quiz_pdf(content, pdf_path)
        await callback.message.answer_document(FSInputFile(pdf_path), caption=f"PDF Quiz: {topic}")
    await send_main_menu(callback.message, state)

# --- PODCAST SECTION ---

@router.message(F.text == "Podcast 🎙")
async def podcast_start(message: Message, state: FSMContext):
    await state.set_state(TutorStates.waiting_podcast_topic)
    await message.answer("Topic for the podcast?", reply_markup=back_menu())

@router.message(TutorStates.waiting_podcast_topic, F.text)
async def handle_podcast_topic(message: Message, state: FSMContext):
    if message.text in ["Main menu 🏠", "Change Level ⚙️"]:
        if message.text == "Change Level ⚙️": await start_cmd(message, state)
        else: await send_main_menu(message, state)
        return
    await state.update_data(topic=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Male 👨", callback_data="voice_male"),
         InlineKeyboardButton(text="Female 👩", callback_data="voice_female")]
    ])
    await state.set_state(TutorStates.waiting_podcast_voice)
    await message.answer("Choose voice:", reply_markup=kb)

@router.callback_query(TutorStates.waiting_podcast_voice, F.data.startswith("voice_"))
async def handle_voice(callback: CallbackQuery, state: FSMContext):
    await state.update_data(voice=callback.data)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 min", callback_data="dur_1"),
         InlineKeyboardButton(text="2 min", callback_data="dur_2")]
    ])
    await state.set_state(TutorStates.waiting_podcast_length)
    await callback.message.edit_text("Duration:", reply_markup=kb)

@router.callback_query(TutorStates.waiting_podcast_length, F.data.startswith("dur_"))
async def finalize_podcast(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    duration = int(callback.data.replace("dur_", ""))
    topic = data.get('topic')
    level = data.get('user_level', 'A1')
    voice_choice = data.get('voice')
    
    await callback.message.edit_text(f"⏳ Generating podcast script...")
    script = await generate_podcast_script(topic, duration, level=level)
    
    tld_choice = 'com.ng' if voice_choice == "voice_male" else 'co.uk'
    tts = gTTS(text=script, lang='en', tld=tld_choice)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "podcast.mp3"
        tts.save(str(path))
        await callback.message.answer_voice(FSInputFile(path), caption=f"🎙 {topic} Podcast")
    await send_main_menu(callback.message, state)

# --- UTILS ---

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:50] or "topic"

async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    print("Bot started successfully!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")