from __future__ import annotations
from typing import Dict, Any, List, Optional
import json
import os
import asyncio
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

load_dotenv()

DEFAULT_LEVEL = os.getenv("DEFAULT_LEVEL", "A1-A2")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_client = None
if OPENAI_API_KEY:
    try:
        from openai import AsyncOpenAI
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"OPENAI ERROR: {e}") # Осы жолды қосып қойсаң, қате терминалда көрінеді
        _client = None


def _fallback_vocabulary(topic: str) -> dict[str, Any]:
    words = [
        ("topic", f"words connected to {topic}", f"I want to learn {topic} words.", "тақырып"),
        ("useful", "helpful and practical", f"This word is useful for daily life.", "пайдалы"),
        ("simple", "easy to understand", f"Please use a simple example.", "қарапайым"),
        ("practice", "do again to improve", f"I practice English every day.", "жаттығу жасау"),
        ("common", "often used", f"Travel is a common topic in class.", "жиі қолданылатын"),
    ]
    return {
        "title": f"Vocabulary: {topic}",
        "level": DEFAULT_LEVEL,
        "intro": f"This PDF helps you learn the topic: {topic}. Read the words, study the examples, and do the mini quiz.",
        "words": [
            {
                "word": w,
                "definition": d,
                "example": e,
                "translation": t,
            }
            for w, d, e, t in words
        ],
        "quiz": [
            {
                "question": f"Make one sentence with '{words[0][0]}'.",
                "answer": "Open answer",
            },
            {
                "question": f"What is one useful word in the topic {topic}?",
                "answer": "Open answer",
            },
            {
                "question": f"Translate one word from this lesson into Kazakh or Russian.",
                "answer": "Open answer",
            },
        ],
        "homework": "Write 3 sentences using the new words.",
    }


def _fallback_grammar(topic: str) -> dict[str, Any]:
    return {
        "title": f"Grammar: {topic}",
        "level": DEFAULT_LEVEL,
        "intro": f"This PDF explains {topic} in a simple way.",
        "formula": "Structure + example + practice",
        "explanation": f"{topic} is used to talk about everyday English clearly and simply.",
        "examples": [
            "I go to school every day.",
            "She does not like coffee.",
            "Do they play football on weekends?",
        ],
        "common_mistakes": [
            "Do not forget the third-person -s in Present Simple: He works.",
            "Use 'do/does' in questions and negatives.",
            "Use a short, clear example sentence.",
        ],
        "exercises": [
            "Make one positive sentence.",
            "Make one negative sentence.",
            "Make one question sentence.",
        ],
        "homework": "Write 5 sentences about your own life.",
    }


def _fallback_dialogue_reply(topic: str, user_text: str) -> dict[str, str]:
    return {
        "reply": f"Nice. I understand you. In a {topic} situation, that sounds natural.",
        "correction": "Try to keep your sentence short and clear.",
        "tip": "Use simple words first, then add details.",
        "question": f"Can you say that again in one more sentence about {topic}?",
    }


async def _ask_llm(system_prompt: str, user_prompt: str):
    print("GPT-ге сұраныс кетті...") # ОСЫ ЖОЛДЫ ҚОС
    if not _client:
        print("OpenAI Client істеп тұрған жоқ!") # ЖӘНЕ ОСЫНЫ
        return None
    try:
        response = await _client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.7,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception:
        return None


async def generate_vocabulary_content(topic: str, count: int = 5 ,level: str = "A1") -> dict[str, Any]:
    system_prompt = f"""
You are an English teacher for {level} learners.
Create a vocabulary lesson for {level} level about: {topic}.
Return ONLY valid JSON with:
title, level, intro, words, quiz, homework.
CRITICAL: The 'words' array MUST have EXACTLY {count} items.
Each word item MUST have: word, definition, example, translation (in Russian).

quiz must be an array of 3 items.
homework: a short task.
Use simple English.
"""
    user_prompt = f"Create a vocabulary lesson with {count} words about: {topic}"
    
    data = await _ask_llm(system_prompt, user_prompt)
    return data if data else _fallback_vocabulary(topic)


async def generate_grammar_content(topic: str,level: str = "A1") -> dict[str, Any]:
    system_prompt = """
You are an English teacher for {level} learners.
Return ONLY valid JSON with:
title, level, intro, formula, explanation, examples, common_mistakes, exercises, homework.

examples must be an array of 3 short sentences.
common_mistakes must be an array of 3 short items.
exercises must be an array of 3 short tasks.
Use simple English. Keep it friendly and clear.
"""
    user_prompt = f"""
Create a grammar lesson about: {topic}

Make it beginner-friendly and practical.
"""
    data = await _ask_llm(system_prompt, user_prompt)
    return data if data else _fallback_grammar(topic)

# content_service.py файлының соңына немесе generate_quiz_content-тен кейін қос:

async def generate_podcast_script(topic: str, duration_min: int,level: str = "A1") -> str:
    """
    GPT-ден берілген тақырып пен уақытқа сай подкаст сценарийін сұрайды.
    duration_min: 1, 2 немесе 3 минут.
    """
    # 1 минутта адам орташа есеппен 130-150 сөз сөйлейді
    word_count = duration_min * 140
    
    system_prompt = f"""
You are an English Podcast Host for {level} learners. 
Your task is to write a natural, engaging podcast script about a specific topic.
Level: {DEFAULT_LEVEL}.
The script must be approximately {word_count} words long (around {duration_min} minute(s) of speaking).

Structure of the script:
1. Intro: Welcome the listeners and introduce the topic.
2. Key Vocabulary: Briefly explain 3-5 important words related to the topic.
3. Main Part: Talk about the topic using simple but natural English.
4. Outro: Summary and a 'goodbye' message.

IMPORTANT: Return ONLY the plain text of the script. No JSON, no headers, just the spoken text.
"""
    user_prompt = f"Write a {duration_min} minute podcast script about the topic: {topic}"

    # _ask_llm функциясын қолданамыз, бірақ бізге JSON емес, мәтін керек болғандықтан 
    # жаңа кішігірім логика қосамыз (немесе _ask_llm-ді сәл өзгертсең болады)
    
    if not _client:
        return f"Hello listeners! Today we are talking about {topic}. This is a simple lesson to help you learn English."

    try:
        response = await _client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.8, # Көбірек 'creative' болуы үшін
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        script = response.choices[0].message.content
        return script if script else "Error generating script."
    except Exception as e:
        print(f"Podcast GPT Error: {e}")
        return f"Welcome! Let's talk about {topic}. This topic is very interesting for English learners."

async def generate_quiz_content(topic: str, count: int = 5, level: str = "A1") -> dict[str, Any]:
    system_prompt = f"""
    You are an English Grammar Expert for {level} learners. Return ONLY valid JSON.
    Create a grammar-focused quiz with EXACTLY {count} multiple choice questions about: {topic}.

    CRITICAL RULES:
    1. Focus ONLY on the grammar rules of "{topic}". 
    2. The options should test the correct form of verbs, pronouns, or sentence structure.
    3. Each question MUST have an "explanation" field (max 200 characters) explaining why the answer is correct.

    Return ONLY valid JSON with this structure:
    {{
      "title": "Grammar Quiz: {topic}",
      "intro": "Test your knowledge of {topic}.",
      "multiple_choice": [
        {{
          "question": "The sentence with a blank...",
          "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
          "answer": "Option 1",
          "explanation": "We use this form because..."
        }}
      ],
      "fill_blank": [],
      "answer_key": "See the explanations in the quiz."
    }}
    
    Use simple English for A1-A2 learners.
    """
    user_prompt = f"Create a grammar quiz with {count} questions about: {topic}"
    data = await _ask_llm(system_prompt, user_prompt)
    
    if data:
        return data

    # Егер GPT-ден жауап келмей қалса, запас нұсқа (Fallback)
    return {
        "title": f"Grammar Check: {topic}",
        "intro": f"Let's practice {topic} grammar.",
        "multiple_choice": [
            {
                "question": f"Complete the sentence according to {topic} rules: I ___ (to be) a student.",
                "options": ["am", "is", "are", "be"],
                "answer": "am",
                "explanation": "With the pronoun 'I', we always use the verb form 'am' in Present Simple."
            }
        ] * count,
        "fill_blank": [],
        "answer_key": "Check the interactive quiz for answers.",
    }