from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Any, List

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from xml.sax.saxutils import escape

def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        ("/Users/adi/Downloads/english_tutor_bot_pro (3)/dejavu-sans/DejaVuSans.ttf", 
         "/Users/adi/Downloads/english_tutor_bot_pro (3)/dejavu-sans/DejaVuSans-Bold.ttf"),
        ("/Library/Fonts/DejaVuSans.ttf", "/Library/Fonts/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf")
    ]
    for regular, bold in candidates:
        if os.path.exists(regular):
            try:
                pdfmetrics.registerFont(TTFont("TutorFont", regular))
                if os.path.exists(bold):
                    pdfmetrics.registerFont(TTFont("TutorFont-Bold", bold))
                else:
                    pdfmetrics.registerFont(TTFont("TutorFont-Bold", regular))
                return "TutorFont", "TutorFont-Bold"
            except Exception:
                pass
    return "Helvetica", "Helvetica-Bold"

FONT_REGULAR, FONT_BOLD = _register_fonts()

def _styles():
    styles = getSampleStyleSheet()
    # Негізгі мәтін стилі (кесте ішінде қолданылады)
    if "TutorBody" not in styles:
        styles.add(
            ParagraphStyle(
                name="TutorBody",
                parent=styles["BodyText"],
                fontName=FONT_REGULAR,
                fontSize=10,
                leading=12,
                alignment=TA_LEFT,
                spaceAfter=6,
            )
        )
    # Тақырып стилі
    if "TutorTitle" not in styles:
        styles.add(
            ParagraphStyle(
                name="TutorTitle",
                parent=styles["Title"],
                fontName=FONT_BOLD,
                fontSize=20,
                leading=24,
                alignment=TA_CENTER,
                spaceAfter=10,
            )
        )
    # Кіші тақырып стилі
    if "TutorSubTitle" not in styles:
        styles.add(
            ParagraphStyle(
                name="TutorSubTitle",
                parent=styles["Heading2"],
                fontName=FONT_BOLD,
                fontSize=12,
                leading=15,
                textColor=colors.HexColor("#2b2b2b"),
                spaceAfter=6,
            )
        )
    # Кіші мәтін стилі (жауаптар үшін)
    if "TutorSmall" not in styles:
        styles.add(
            ParagraphStyle(
                name="TutorSmall",
                parent=styles["BodyText"],
                fontName=FONT_REGULAR,
                fontSize=9,
                leading=11,
                spaceAfter=4,
            )
        )
    return styles

def _para(text: str, style) -> Paragraph:
    # escape-ті алып тастаймыз немесе тек қажетсіз белгілерді тазалаймыз
    # ReportLab Paragraph-ы <i> және <b> тегтерін өзі түсінеді
    clean_text = str(text).replace("\n", "<br/>")
    return Paragraph(clean_text, style)

def _build_doc(story, output_path: Path):
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    doc.build(story)

def build_vocabulary_pdf(content: Dict[str, Any], output_path: Path):
    styles = _styles()
    story = []
    
    # Сөздердің нақты санын есептеу
    words_list = content.get("words", [])
    words_count = len(words_list)
    
    # Тақырып және кіріспе
    story.append(_para(content.get("title", "Vocabulary"), styles["TutorTitle"]))
    story.append(_para(content.get("intro", ""), styles["TutorBody"]))
    story.append(Spacer(1, 10))
    
    # ТҮЗЕТУ: "5" санының орнына нақты санды қойдық
    story.append(_para(f"{words_count} Key Words", styles["TutorSubTitle"]))

    # Кесте стилі
    cell_style = styles["TutorBody"]
    header_style = ParagraphStyle(name="HeaderStyle", parent=cell_style, fontName=FONT_BOLD)

    # Кесте басы
    rows = [[
        _para("Word", header_style),
        _para("Meaning", header_style),
        _para("Translation", header_style),
        _para("Example", header_style)
    ]]

    # ТҮЗЕТУ: [:5] шектеуін алып тастадық, енді барлық сөз шығады
    for item in words_list:
        rows.append([
            _para(item.get("word", ""), cell_style),
            _para(item.get("definition", ""), cell_style),
            _para(item.get("translation", ""), cell_style),
            _para(item.get("example", ""), cell_style),
        ])

    # Кестені құру
    table = Table(rows, colWidths=[25*mm, 55*mm, 35*mm, 60*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f0fe")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b7c4d6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fbff")]),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 15))

    # Mini Quiz section with safety check
    story.append(_para("Mini Quiz", styles["TutorSubTitle"]))
    
    for i, quiz in enumerate(content.get("quiz", []), start=1):
        # We check if 'quiz' is a dictionary to prevent 'AttributeError'
        if isinstance(quiz, dict):
            q_text = quiz.get('question', '')
            a_text = quiz.get('answer', '')
        else:
            # If GPT returns a simple string instead of a dictionary
            q_text = str(quiz)
            a_text = "Check your understanding above."

        story.append(_para(f"{i}. {q_text}", styles["TutorBody"]))
        story.append(_para(f"<i>Answer key: {a_text}</i>", styles["TutorSmall"]))
        story.append(Spacer(1, 4))

    # Homework section
    story.append(Spacer(1, 10))
    story.append(_para(f"<b>Homework:</b> {content.get('homework', '')}", styles["TutorBody"]))
    
    _build_doc(story, output_path)

def build_grammar_pdf(content: Dict[str, Any], output_path: Path):
    styles = _styles()
    story = []
    
    # Тақырып және кіріспе
    story.append(_para(content.get("title", "Grammar Lesson"), styles["TutorTitle"]))
    story.append(_para(content.get("intro", ""), styles["TutorBody"]))
    story.append(Spacer(1, 10))

    # Секциялар тізімі (Формула, Түсіндірме, Мысалдар, Қателер, Жаттығулар)
    sections = [
        ("Formula 📐", "formula"),
        ("Explanation 💡", "explanation"),
        ("Examples 📝", "examples"),
        ("Common Mistakes ⚠️", "common_mistakes"),
        ("Exercises ✍️", "exercises")
    ]
    
    for label, key in sections:
        data = content.get(key, "")
        if data:
            story.append(_para(label, styles["TutorSubTitle"]))
            if isinstance(data, list):
                for item in data[:4]: # Алғашқы 4 мысалды көрсету
                    story.append(_para(f"• {item}", styles["TutorBody"]))
            else:
                story.append(_para(data, styles["TutorBody"]))
            story.append(Spacer(1, 8))

    # Үй тапсырмасы
    if content.get("homework"):
        story.append(Spacer(1, 5))
        story.append(_para(f"<b>Homework:</b> {content.get('homework', '')}", styles["TutorBody"]))
    
    _build_doc(story, output_path)


def build_quiz_pdf(content: Dict[str, Any], output_path: Path):
    styles = _styles()
    story = []
    
    # Тақырып және кіріспе
    story.append(_para(content.get("title", "Practice Quiz"), styles["TutorTitle"]))
    story.append(_para(content.get("intro", "Test your knowledge!"), styles["TutorBody"]))
    story.append(Spacer(1, 12))

    # 1. Көп нұсқалы сұрақтар (Multiple Choice) - Грамматикалық бағыт
    if content.get("multiple_choice"):
        story.append(_para("Multiple Choice Questions", styles["TutorSubTitle"]))
        for i, q in enumerate(content.get("multiple_choice", []), start=1):
            # Сұрақ
            story.append(_para(f"{i}. {q.get('question', '')}", styles["TutorBody"]))
            
            # Жауап нұсқалары
            for opt in q.get("options", []):
                story.append(_para(f"  ○ {opt}", styles["TutorSmall"]))
            
            # Дұрыс жауабы
            story.append(_para(f"<i>Answer: {q.get('answer', '')}</i>", styles["TutorSmall"]))
            
            # Түсіндірме (Explanation) - егер GPT-ден келсе, PDF-ке де шығарамыз
            if q.get("explanation"):
                story.append(_para(f"<b>Explanation:</b> {q.get('explanation')}", styles["TutorSmall"]))
            
            story.append(Spacer(1, 8))

    # 2. Сөйлемді толықтыру (Fill in the blanks)
    if content.get("fill_blank"):
        story.append(Spacer(1, 10))
        story.append(_para("Fill in the Blanks", styles["TutorSubTitle"]))
        for i, q in enumerate(content.get("fill_blank", []), start=1):
            story.append(_para(f"{i}. {q.get('sentence', '_______')}", styles["TutorBody"]))
            story.append(_para(f"<i>Correct word: {q.get('answer', '')}</i>", styles["TutorSmall"]))
            
            # Сөйлемді толтыруға да түсіндірме болса қосамыз
            if q.get("explanation"):
                story.append(_para(f"<b>Explanation:</b> {q.get('explanation')}", styles["TutorSmall"]))
            
            story.append(Spacer(1, 6))

    _build_doc(story, output_path)

def build_speaking_pdf(content: Dict[str, Any], output_path: Path):
    """Сөйлеу дағдысын дамытуға арналған PDF"""
    styles = _styles()
    story = []
    
    story.append(_para(content.get("title", "Speaking Practice"), styles["TutorTitle"]))
    story.append(_para(content.get("intro", ""), styles["TutorBody"]))
    story.append(Spacer(1, 10))

    # Талқылау сұрақтары
    if content.get("discussion_questions"):
        story.append(_para("Discussion Questions 🗣️", styles["TutorSubTitle"]))
        for i, q in enumerate(content.get("discussion_questions", []), start=1):
            story.append(_para(f"{i}. {q}", styles["TutorBody"]))
            story.append(Spacer(1, 4))

    # Пайдалы фразалар
    if content.get("useful_phrases"):
        story.append(Spacer(1, 10))
        story.append(_para("Useful Phrases for this Topic", styles["TutorSubTitle"]))
        for phrase in content.get("useful_phrases", []):
            story.append(_para(f"• {phrase}", styles["TutorBody"]))

    # Рөлдік ойын (Scenario)
    if content.get("scenario"):
        story.append(Spacer(1, 10))
        story.append(_para("Role-play Scenario 🎭", styles["TutorSubTitle"]))
        story.append(_para(content.get("scenario", ""), styles["TutorBody"]))

    story.append(Spacer(1, 15))
    story.append(_para(f"<b>Speaking Homework:</b> {content.get('homework', 'Record your voice and listen to it.')}", styles["TutorBody"]))
    
    _build_doc(story, output_path)