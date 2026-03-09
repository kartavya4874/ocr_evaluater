"""
Calibration module — learns faculty marking style from pre-graded answer sheets.
Scans for examiner_marks_written and builds a calibration profile per course.
"""

import json
import logging
from typing import List, Dict, Optional, Any

from openai import OpenAI

logger = logging.getLogger(__name__)


async def find_pregraded_answers(student_ocr_list: List[dict]) -> List[dict]:
    """
    Scan all student OCR results for answers with examiner_marks_written.
    Returns a list of {question_number, answer, examiner_mark, roll_number}.
    """
    pregraded = []
    for student_ocr in student_ocr_list:
        roll = student_ocr.get("roll_number", "unknown")
        for ans in student_ocr.get("answers", []):
            if ans.get("examiner_marks_written") is not None:
                pregraded.append({
                    "question_number": ans["question_number"],
                    "answer_text": ans.get("answer_text", ""),
                    "diagram_description": ans.get("diagram_description", ""),
                    "code_written": ans.get("code_written", ""),
                    "math_expression": ans.get("math_expression", ""),
                    "chemistry_notation": ans.get("chemistry_notation", ""),
                    "examiner_mark": ans["examiner_marks_written"],
                    "roll_number": roll,
                })
    return pregraded


async def build_calibration_profile(
    pregraded_answers: List[dict],
    question_map: Dict[str, dict],
    answer_key_map: Dict[str, dict],
    api_key: str,
) -> dict:
    """
    Build a calibration profile by having GPT-4o infer marking criteria from
    pre-graded answers.
    """
    if not pregraded_answers:
        return {"examples": [], "criteria_summary": "No pre-graded answers found for calibration."}

    # Group by question number
    by_question: Dict[str, List[dict]] = {}
    for pg in pregraded_answers:
        qnum = pg["question_number"]
        if qnum not in by_question:
            by_question[qnum] = []
        by_question[qnum].append(pg)

    calibration_examples = []
    criteria_parts = []

    client = OpenAI(api_key=api_key)

    for qnum, answers in by_question.items():
        qinfo = question_map.get(qnum, {})
        akinfo = answer_key_map.get(qnum, {})

        # Build examples text
        examples_text = ""
        for ans in answers[:5]:  # Max 5 examples per question
            examples_text += f"\n--- Student {ans['roll_number']} ---\n"
            examples_text += f"Answer: {ans['answer_text']}\n"
            if ans.get("code_written"):
                examples_text += f"Code: {ans['code_written']}\n"
            if ans.get("math_expression"):
                examples_text += f"Math: {ans['math_expression']}\n"
            examples_text += f"Faculty mark: {ans['examiner_mark']} / {qinfo.get('marks_allocated', akinfo.get('full_marks', 0))}\n"

        prompt = f"""Analyze the faculty's marking pattern for this question.

Question {qnum}: {qinfo.get('question_text', 'N/A')}
Type: {qinfo.get('question_type', 'SHORT')}
Max marks: {qinfo.get('marks_allocated', akinfo.get('full_marks', 0))}
Correct answer: {akinfo.get('correct_answer', 'N/A')}
Keywords: {akinfo.get('acceptable_keywords', [])}

Pre-graded examples:
{examples_text}

Based on these examples, infer:
1. How strictly does this faculty grade?
2. What partial credit patterns do they follow?
3. What keywords or steps do they specifically care about?
4. Any leniency patterns?

Return ONLY valid JSON:
{{
  "question_number": "{qnum}",
  "strictness": "LENIENT|MODERATE|STRICT",
  "partial_credit_pattern": "<description>",
  "key_criteria": ["<criterion1>", "<criterion2>"],
  "leniency_notes": "<any patterns of leniency>",
  "example_calibrations": [
    {{
      "answer_quality": "brief description",
      "marks_given": <number>,
      "marks_possible": <number>
    }}
  ]
}}"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                lines = text.split("\n")[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)

            cal = json.loads(text)
            calibration_examples.append(cal)
            criteria_parts.append(
                f"Q{qnum}: {cal.get('strictness', 'MODERATE')} grading — {cal.get('partial_credit_pattern', 'standard')}"
            )
        except Exception as e:
            logger.warning(f"Calibration inference failed for Q{qnum}: {e}")
            continue

    return {
        "examples": calibration_examples,
        "criteria_summary": "; ".join(criteria_parts) if criteria_parts else "Standard grading — no calibration data.",
    }


def format_calibration_for_prompt(calibration_profile: dict, question_number: str) -> str:
    """Format calibration data as few-shot examples for the evaluation prompt."""
    if not calibration_profile or not calibration_profile.get("examples"):
        return "No calibration data available. Use standard academic grading."

    # Find calibration for this specific question
    relevant = [
        ex for ex in calibration_profile["examples"]
        if ex.get("question_number") == question_number
    ]

    if not relevant:
        # Use general calibration summary
        return f"General marking calibration: {calibration_profile.get('criteria_summary', 'Standard grading')}"

    cal = relevant[0]
    parts = [
        f"Faculty marking style for Q{question_number}:",
        f"  Strictness: {cal.get('strictness', 'MODERATE')}",
        f"  Partial credit: {cal.get('partial_credit_pattern', 'N/A')}",
        f"  Key criteria: {', '.join(cal.get('key_criteria', []))}",
    ]

    if cal.get("leniency_notes"):
        parts.append(f"  Leniency: {cal['leniency_notes']}")

    if cal.get("example_calibrations"):
        parts.append("  Examples:")
        for ex in cal["example_calibrations"][:3]:
            parts.append(f"    - {ex.get('answer_quality', 'N/A')}: {ex.get('marks_given', 0)}/{ex.get('marks_possible', 0)}")

    return "\n".join(parts)
