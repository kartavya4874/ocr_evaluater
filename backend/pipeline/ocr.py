"""
OCR module — uses GPT-4o vision to extract structured data from exam documents.
Handles PDFs (via pdf2image) and direct image files.
"""

import base64
import json
import logging
import asyncio
from pathlib import Path
from typing import List, Optional

from openai import OpenAI
from PIL import Image

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff"}


def _convert_pdf_to_images(pdf_path: str) -> List[str]:
    """Convert a PDF file to a list of base64-encoded JPEG images."""
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, dpi=200, fmt="jpeg")
        base64_images = []
        for img in images:
            import io
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            base64_images.append(b64)
        return base64_images
    except Exception as e:
        logger.error(f"PDF conversion failed for {pdf_path}: {e}")
        raise


def _load_image_as_base64(image_path: str) -> str:
    """Load an image file and return base64-encoded JPEG."""
    try:
        img = Image.open(image_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        import io
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        logger.error(f"Image loading failed for {image_path}: {e}")
        raise


def get_images_base64(file_path: str) -> List[str]:
    """Convert any supported file to a list of base64 JPEG images."""
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        return _convert_pdf_to_images(file_path)
    elif ext in SUPPORTED_IMAGE_EXTENSIONS:
        return [_load_image_as_base64(file_path)]
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _build_vision_content(images_b64: List[str], prompt: str) -> list:
    """Build the content array for OpenAI vision API call."""
    content = []
    for b64 in images_b64:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{b64}",
            },
        })
    content.append({
        "type": "text",
        "text": prompt,
    })
    return content


def _parse_json_response(text: str) -> dict:
    """Parse the model's response, stripping any markdown fences."""
    text = text.strip()
    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return json.loads(text)


async def ocr_question_paper(file_path: str, api_key: str) -> dict:
    """OCR a question paper and return structured JSON."""
    print(f"{"*"*15}\n\nCame to question_ocr\n\n{"*"*15}")
    images = get_images_base64(file_path)

    prompt = """You are an expert OCR system. Extract all questions from this exam question paper.

Return ONLY valid JSON. No markdown, no backticks, no explanation.

Return this exact structure:
{
  "total_marks": <number>,
  "questions": [
    {
      "question_number": "<string like 1, 1a, 2b etc>",
      "question_text": "<full question text>",
      "question_type": "<one of: MCQ, FIB, SHORT, LONG, DIAGRAM, CODE, MATH, CHEMISTRY, NUMERICAL>",
      "marks_allocated": <number>,
      "options": ["A. ...", "B. ..."],
      "sub_questions": [
        {
          "question_number": "<e.g. 1a>",
          "question_text": "...",
          "question_type": "...",
          "marks_allocated": <number>,
          "options": [],
          "special_instruction": null
        }
      ],
      "special_instruction": "<e.g. 'attempt any 3 of 5' or null>"
    }
  ]
}

Rules:
- Extract EVERY question and sub-question
- Correctly identify question types
- Include marks allocated for each question
- If marks are not specified for a question, estimate from total marks
- Preserve mathematical notation as LaTeX where possible
- For MCQs, include all options
- Note any special instructions (attempt any N, compulsory, etc.)"""

    client = OpenAI(api_key=api_key)
    content = _build_vision_content(images, prompt)

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=8192,
        messages=[{"role": "user", "content": content}],
    )

    text = response.choices[0].message.content
    return _parse_json_response(text)


async def ocr_answer_key(file_path: str, api_key: str) -> dict:
    """OCR an answer key and return structured JSON."""
    print(f"{"*"*15}\n\nCame to Key_answer\n\n{"*"*15}")
    images = get_images_base64(file_path)

    prompt = """You are an expert OCR system. Extract all answers from this exam answer key.

Return ONLY valid JSON. No markdown, no backticks, no explanation.

Return this exact structure:
{
  "answers": [
    {
      "question_number": "<string like 1, 1a, 2b etc>",
      "correct_answer": "<the full correct answer>",
      "acceptable_keywords": ["keyword1", "keyword2"],
      "marking_scheme": "<description of how marks should be awarded>",
      "full_marks": <number>,
      "negative_marks": <number, 0 if none>,
      "step_marks": [
        {"step": "<description of step>", "marks": <number>}
      ]
    }
  ]
}

Rules:
- Extract EVERY answer
- Include all acceptable keywords and variations
- Extract step-by-step marking schemes where present
- Include negative marking info if specified
- Preserve mathematical notation
- For MCQs, just the correct option letter and text"""

    client = OpenAI(api_key=api_key)
    content = _build_vision_content(images, prompt)

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=8192,
        messages=[{"role": "user", "content": content}],
    )

    text = response.choices[0].message.content
    return _parse_json_response(text)


async def ocr_answer_sheet(file_path: str, api_key: str, roll_number_hint: str = "") -> dict:
    """OCR a student answer sheet and return structured JSON."""
    print(f"{"*"*15}\n\nCame to ocr_Answer\n\n{"*"*15}")
    images = get_images_base64(file_path)

    prompt = f"""You are an expert OCR system. Extract all student answers from this exam answer sheet.
The expected roll number from the filename is: {roll_number_hint}

Return ONLY valid JSON. No markdown, no backticks, no explanation.

Return this exact structure:
{{
  "roll_number": "<extracted or use hint: {roll_number_hint}>",
  "answers": [
    {{
      "question_number": "<string like 1, 1a, 2b etc>",
      "answer_text": "<the student's written answer>",
      "diagram_description": "<describe any diagram drawn, empty if none>",
      "code_written": "<any code written, empty if none>",
      "math_expression": "<any math expressions, empty if none>",
      "chemistry_notation": "<any chemistry notation, empty if none>",
      "is_blank": <true if question was left blank>,
      "is_crossed_out": <true if answer was crossed out>,
      "legibility": "<HIGH, MEDIUM, or LOW>",
      "examiner_marks_written": <number if faculty already wrote marks on this question, null otherwise>
    }}
  ]
}}

Rules:
- Extract EVERY answer the student wrote, matching question numbers
- Note blank/unattempted questions as is_blank: true
- Note crossed out answers as is_crossed_out: true
- Rate legibility honestly
- If faculty/examiner has written marks on specific questions, capture those in examiner_marks_written
- Preserve all mathematical notation, code, chemical formulas exactly
- Describe any diagrams in detail
- If roll number is visible on the sheet, use that; otherwise use the hint"""

    client = OpenAI(api_key=api_key)
    content = _build_vision_content(images, prompt)

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=8192,
        messages=[{"role": "user", "content": content}],
    )

    text = response.choices[0].message.content
    return _parse_json_response(text)
