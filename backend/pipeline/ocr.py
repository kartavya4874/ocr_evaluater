"""
OCR module — uses Google Cloud Vision API for text extraction,
then structures the raw text into JSON using OpenAI GPT-4o.
Handles PDFs (via pdf2image) and direct image files.
"""

import base64
import json
import logging
import asyncio
import io
from pathlib import Path
from typing import List, Optional

from google.cloud import vision
from google.oauth2 import service_account
from openai import OpenAI
from PIL import Image

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff"}

# ─── Exam Structure Template ────────────────────────────────────────────────
# This describes the standard end-semester exam paper format.
# Used as context for the AI to correctly parse question papers.
EXAM_STRUCTURE_CONTEXT = """
IMPORTANT — Standard End-Semester Exam Paper Structure:
The question paper has THREE compulsory parts:

  Part A: Q.No. 1 to 10 — 2 marks each (total 20 marks)
    - All questions are compulsory
    - Typically SHORT answer or MCQ or FIB type
    - No internal choice

  Part B: Q.No. 11 to 15 — 6 marks each (total 30 marks)
    - Each question has an INTERNAL CHOICE (OR option)
    - e.g. Q11 has two options: 11a OR 11b — student answers only ONE
    - Both options carry the same marks (6 marks)

  Part C: Q.No. 16 to 20 — 10 marks each (total 50 marks)
    - Each question has an INTERNAL CHOICE (OR option)
    - e.g. Q16 has two options: 16a OR 16b — student answers only ONE
    - Both options carry the same marks (10 marks)

  Total Marks: 100

Internal Choice Rules:
- When a question has "OR" between two sub-parts, it means INTERNAL CHOICE
- The student must answer ONLY ONE of the two choices
- Both choices carry equal marks
- Mark the special_instruction as "INTERNAL_CHOICE" for such questions
- Use has_internal_choice: true for the parent question
- Use choice_group to link the two options (e.g. "11_OR" for Q11a and Q11b)
"""


def _get_vision_client(credentials_path: str) -> vision.ImageAnnotatorClient:
    """Create a Google Cloud Vision client from a service account JSON file."""
    credentials = service_account.Credentials.from_service_account_file(credentials_path)
    return vision.ImageAnnotatorClient(credentials=credentials)


def _convert_pdf_to_images(pdf_path: str) -> List[bytes]:
    """Convert a PDF file to a list of JPEG image bytes."""
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, dpi=200, fmt="jpeg")
        image_bytes_list = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            image_bytes_list.append(buf.getvalue())
        return image_bytes_list
    except Exception as e:
        logger.error(f"PDF conversion failed for {pdf_path}: {e}")
        raise


def _load_image_as_bytes(image_path: str) -> bytes:
    """Load an image file and return JPEG bytes."""
    try:
        img = Image.open(image_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue()
    except Exception as e:
        logger.error(f"Image loading failed for {image_path}: {e}")
        raise


def get_image_bytes_list(file_path: str) -> List[bytes]:
    """Convert any supported file to a list of JPEG image byte arrays."""
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        return _convert_pdf_to_images(file_path)
    elif ext in SUPPORTED_IMAGE_EXTENSIONS:
        return [_load_image_as_bytes(file_path)]
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _extract_text_with_vision(image_bytes_list: List[bytes], credentials_path: str) -> str:
    """
    Use Google Cloud Vision API to perform OCR on a list of images.
    Returns the combined extracted text from all pages/images.
    """
    client = _get_vision_client(credentials_path)
    all_text = []

    for idx, img_bytes in enumerate(image_bytes_list):
        image = vision.Image(content=img_bytes)

        # Use document_text_detection for better structured text extraction
        response = client.document_text_detection(image=image)

        if response.error.message:
            raise Exception(
                f"Google Vision API error on page {idx + 1}: {response.error.message}"
            )

        if response.full_text_annotation:
            page_text = response.full_text_annotation.text
            all_text.append(f"--- Page {idx + 1} ---\n{page_text}")
        else:
            all_text.append(f"--- Page {idx + 1} ---\n[No text detected]")

    return "\n\n".join(all_text)


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


async def ocr_question_paper(file_path: str, api_key: str, credentials_path: str = "") -> dict:
    """
    OCR a question paper using Google Vision API for text extraction,
    then use OpenAI GPT-4o to structure the extracted text into JSON.
    """
    print(f"{'*'*15}\n\nCame to question_ocr (Google Vision + OpenAI)\n\n{'*'*15}")

    # Step 1: Extract raw text using Google Cloud Vision
    image_bytes = get_image_bytes_list(file_path)
    raw_text = _extract_text_with_vision(image_bytes, credentials_path)
    logger.info(f"Google Vision OCR extracted {len(raw_text)} characters from question paper")

    # Step 2: Use OpenAI to structure the raw OCR text
    prompt = f"""You are an expert exam data structuring system. You have been given raw OCR text 
extracted from an exam question paper using Google Cloud Vision API.

{EXAM_STRUCTURE_CONTEXT}

Your job is to parse and structure this text into a well-organized JSON format following the exam structure described above.

RAW OCR TEXT:
{raw_text}

Return ONLY valid JSON. No markdown, no backticks, no explanation.

Return this exact structure:
{{
  "total_marks": <number>,
  "parts": [
    {{
      "part_name": "Part A",
      "question_range": "1-10",
      "marks_per_question": 2,
      "has_internal_choice": false,
      "total_marks": 20
    }},
    {{
      "part_name": "Part B",
      "question_range": "11-15",
      "marks_per_question": 6,
      "has_internal_choice": true,
      "total_marks": 30
    }},
    {{
      "part_name": "Part C",
      "question_range": "16-20",
      "marks_per_question": 10,
      "has_internal_choice": true,
      "total_marks": 50
    }}
  ],
  "questions": [
    {{
      "question_number": "<string like 1, 11, 16 etc>",
      "question_text": "<full question text>",
      "question_type": "<one of: MCQ, FIB, SHORT, LONG, DIAGRAM, CODE, MATH, CHEMISTRY, NUMERICAL>",
      "marks_allocated": <number>,
      "part": "<Part A, Part B, or Part C>",
      "has_internal_choice": <true if this question has an OR option>,
      "options": ["A. ...", "B. ..."],
      "sub_questions": [
        {{
          "question_number": "<e.g. 11a>",
          "question_text": "...",
          "question_type": "...",
          "marks_allocated": <number>,
          "options": [],
          "choice_group": "<e.g. '11_OR' — links two OR choices together>",
          "special_instruction": "<'INTERNAL_CHOICE' if this is one of two OR options, else null>"
        }}
      ],
      "special_instruction": "<'INTERNAL_CHOICE' if has OR option, or other instructions, or null>"
    }}
  ]
}}

Rules:
- Extract EVERY question and sub-question from the OCR text
- Part A (Q1-Q10): 2 marks each, all compulsory, no internal choice
- Part B (Q11-Q15): 6 marks each, each has internal choice (OR)
- Part C (Q16-Q20): 10 marks each, each has internal choice (OR)
- For questions with internal choice (OR):
  * Create sub_questions with the two options (e.g. 11a, 11b)
  * Set has_internal_choice: true on the parent
  * Set special_instruction: "INTERNAL_CHOICE" on each sub-question
  * Set choice_group: "<question_number>_OR" on each sub-question (e.g. "11_OR")
  * Both sub-questions get the SAME marks as the parent (6 or 10)
- Correctly identify question types
- Preserve mathematical notation as LaTeX where possible
- For MCQs, include all options
- Fix any OCR artifacts or misrecognized characters intelligently
- If the paper doesn't exactly follow the 3-part structure, adapt but still capture internal choices"""

    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.choices[0].message.content
    return _parse_json_response(text)


async def ocr_answer_key(file_path: str, api_key: str, credentials_path: str = "") -> dict:
    """
    OCR an answer key using Google Vision API for text extraction,
    then use OpenAI GPT-4o to structure the extracted text into JSON.
    """
    print(f"{'*'*15}\n\nCame to Key_answer (Google Vision + OpenAI)\n\n{'*'*15}")

    # Step 1: Extract raw text using Google Cloud Vision
    image_bytes = get_image_bytes_list(file_path)
    raw_text = _extract_text_with_vision(image_bytes, credentials_path)
    logger.info(f"Google Vision OCR extracted {len(raw_text)} characters from answer key")

    # Step 2: Use OpenAI to structure the raw OCR text
    prompt = f"""You are an expert exam data structuring system. You have been given raw OCR text 
extracted from an exam answer key using Google Cloud Vision API.

{EXAM_STRUCTURE_CONTEXT}

Your job is to parse and structure this text into a well-organized JSON format.
Remember: Part B (Q11-Q15) and Part C (Q16-Q20) have INTERNAL CHOICE (OR options).
The answer key will have answers for BOTH choices (e.g. both 11a and 11b).

RAW OCR TEXT:
{raw_text}

Return ONLY valid JSON. No markdown, no backticks, no explanation.

Return this exact structure:
{{
  "answers": [
    {{
      "question_number": "<string like 1, 11a, 11b, 16a, 16b etc>",
      "correct_answer": "<the full correct answer>",
      "acceptable_keywords": ["keyword1", "keyword2"],
      "marking_scheme": "<description of how marks should be awarded>",
      "full_marks": <number>,
      "negative_marks": <number, 0 if none>,
      "choice_group": "<e.g. '11_OR' if this is an internal choice option, null otherwise>",
      "step_marks": [
        {{"step": "<description of step>", "marks": <number>}}
      ]
    }}
  ]
}}

Rules:
- Extract EVERY answer — including BOTH options for internal choice questions
- For internal choice questions (Q11-Q15, Q16-Q20), provide answers for BOTH choices (a and b)
- Set choice_group to link paired choices (e.g. "11_OR" for both 11a and 11b)
- Part A answers (Q1-Q10): 2 marks each
- Part B answers (Q11a/b-Q15a/b): 6 marks each
- Part C answers (Q16a/b-Q20a/b): 10 marks each
- Include all acceptable keywords and variations
- Extract step-by-step marking schemes where present
- Include negative marking info if specified
- Preserve mathematical notation
- For MCQs, just the correct option letter and text
- Fix any OCR artifacts or misrecognized characters intelligently"""

    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.choices[0].message.content
    return _parse_json_response(text)


async def ocr_answer_sheet(file_path: str, api_key: str, roll_number_hint: str = "", credentials_path: str = "") -> dict:
    """
    OCR a student answer sheet using Google Vision API for text extraction,
    then use OpenAI GPT-4o to structure the extracted text into JSON.
    """
    print(f"{'*'*15}\n\nCame to ocr_Answer (Google Vision + OpenAI)\n\n{'*'*15}")

    # Step 1: Extract raw text using Google Cloud Vision
    image_bytes = get_image_bytes_list(file_path)
    raw_text = _extract_text_with_vision(image_bytes, credentials_path)
    logger.info(f"Google Vision OCR extracted {len(raw_text)} characters from answer sheet")

    # Step 2: Use OpenAI to structure the raw OCR text
    prompt = f"""You are an expert exam data structuring system. You have been given raw OCR text 
extracted from a student's exam answer sheet using Google Cloud Vision API.

{EXAM_STRUCTURE_CONTEXT}

The expected roll number from the filename is: {roll_number_hint}

CRITICAL: For questions with internal choice (Part B: Q11-Q15, Part C: Q16-Q20),
the student will answer ONLY ONE of the two options (either 'a' or 'b').
The other option should NOT be listed — only extract what the student actually wrote.

Your job is to parse and structure this text into a well-organized JSON format.

RAW OCR TEXT:
{raw_text}

Return ONLY valid JSON. No markdown, no backticks, no explanation.

Return this exact structure:
{{
  "roll_number": "<extracted or use hint: {roll_number_hint}>",
  "answers": [
    {{
      "question_number": "<string like 1, 2, 11a, 16b etc>",
      "answer_text": "<the student's written answer>",
      "diagram_description": "<describe any diagram drawn, empty if none>",
      "code_written": "<any code written, empty if none>",
      "math_expression": "<any math expressions, empty if none>",
      "chemistry_notation": "<any chemistry notation, empty if none>",
      "is_blank": <true if question was left blank>,
      "is_crossed_out": <true if answer was crossed out>,
      "legibility": "<HIGH, MEDIUM, or LOW>",
      "examiner_marks_written": <number if faculty already wrote marks on this question, null otherwise>,
      "choice_group": "<e.g. '11_OR' if this is an internal choice answer, null for Part A>"
    }}
  ]
}}

Rules:
- Part A (Q1-Q10): All compulsory, extract all 10 answers
- Part B (Q11-Q15): Student answers only ONE option per question (e.g. 11a OR 11b)
  * Only extract the option the student actually wrote
  * Set choice_group to "<qnum>_OR" (e.g. "11_OR")
- Part C (Q16-Q20): Same as Part B — one option per question
  * Set choice_group to "<qnum>_OR" (e.g. "16_OR")
- Note blank/unattempted questions as is_blank: true
- Note crossed out answers as is_crossed_out: true
- Rate legibility based on OCR confidence
- If faculty/examiner has written marks, capture in examiner_marks_written
- Preserve all mathematical notation, code, chemical formulas exactly
- Describe any diagrams in detail
- If roll number is visible in the text, use that; otherwise use the hint
- Fix any OCR artifacts or misrecognized characters intelligently"""

    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.choices[0].message.content
    return _parse_json_response(text)
