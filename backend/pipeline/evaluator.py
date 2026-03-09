"""
Evaluator module — per-question evaluation using GPT-4o.
Two-phase approach: self-evaluate first, then compare with teacher marks.
Includes post-processing for MCQ/FIB force full-or-zero logic.
"""

import json
import logging
import asyncio
from typing import List, Dict, Optional, Any

import openai
from openai import OpenAI

from backend.pipeline.calibration import format_calibration_for_prompt

logger = logging.getLogger(__name__)


async def evaluate_question(
    mapped_question: dict,
    calibration_profile: dict,
    api_key: str,
    semaphore: Optional[asyncio.Semaphore] = None,
) -> dict:
    """
    Evaluate a single question using GPT-4o.
    Two-phase: (1) self-evaluate without seeing teacher marks, (2) compare & flag.
    """
    if not mapped_question.get("attempted", True):
        return {
            "question_number": mapped_question["question_number"],
            "marks_awarded": 0,
            "marks_total": mapped_question.get("full_marks", mapped_question.get("marks_allocated", 0)),
            "reasoning": "Question not attempted.",
            "student_feedback": "This question was not attempted.",
            "keywords_matched": [],
            "keywords_missing": mapped_question.get("acceptable_keywords", []),
            "flag": mapped_question.get("flag", "UNATTEMPTED"),
            "flag_detail": "Question was blank, crossed out, or missing.",
            "attempted": False,
        }

    student_ans = mapped_question.get("student_answer", {})
    qnum = mapped_question["question_number"]
    qtype = mapped_question.get("question_type", "SHORT")
    marks = mapped_question.get("full_marks", mapped_question.get("marks_allocated", 0))

    calibration_text = format_calibration_for_prompt(calibration_profile, qnum)

    # --- PHASE 1: Self-evaluate WITHOUT seeing teacher marks ---
    # Intentionally exclude examiner_marks_written from the prompt
    prompt = f"""You are a university examiner. Evaluate this answer thoroughly and fairly.
Give the student benefit of the doubt where reasonable.

CALIBRATION — match this faculty's general marking style:
{calibration_text}

Question {qnum} | Type: {qtype} | Max: {marks}
Question: {mapped_question.get('question_text', 'N/A')}
Answer Key: {mapped_question.get('correct_answer', 'N/A')}
Keywords: {mapped_question.get('acceptable_keywords', [])}
Marking Scheme: {mapped_question.get('marking_scheme', 'N/A')}
Step Marks: {json.dumps(mapped_question.get('step_marks', []))}

Student Answer:
Text: {student_ans.get('answer_text', '')}
Diagram: {student_ans.get('diagram_description', '')}
Code: {student_ans.get('code_written', '')}
Math: {student_ans.get('math_expression', '')}
Chemistry: {student_ans.get('chemistry_notation', '')}
Legibility: {student_ans.get('legibility', 'HIGH')}

MARKING RULES — STRICTLY ENFORCED:
- MCQ → full marks or zero. Never partial.
- FIB → full marks or zero. Never partial.
- SHORT/LONG → award partial marks generously based on keyword coverage, accuracy, and relevance. If the answer is broadly correct but poorly phrased, still award significant marks.
- DIAGRAM → partial: labeling, accuracy, completeness. A roughly correct diagram deserves credit.
- CODE → partial: correct logic earns method marks even with syntax errors. Pseudocode or near-correct code should get partial credit.
- MATH → step marks: right method + wrong arithmetic = method marks. Each correct step deserves credit even if final answer wrong.
- CHEMISTRY → partial: formula correctness, balancing, mechanism steps.
- NUMERICAL → method marks even if final answer is wrong. Show work = partial credit.
- LOW LEGIBILITY → reduce marks by 20% (NOT zero), unless completely unreadable.
- Never exceed maximum marks.
- BENEFIT OF DOUBT: If the student's answer demonstrates understanding of the core concept, award marks even if exact wording differs from answer key.
- Consider ALL forms of answer (text, diagram, code, math) together — a weak text answer supported by a correct diagram deserves full credit.
- Do NOT award 0 marks unless the answer is completely wrong, irrelevant, or blank.

Return ONLY valid JSON:
{{
  "question_number": "{qnum}",
  "marks_awarded": <number>,
  "marks_total": {marks},
  "reasoning": "<detailed evaluation reasoning, explain step by step why marks were awarded or deducted>",
  "student_feedback": "<constructive feedback for the student>",
  "keywords_matched": ["<matched keywords>"],
  "keywords_missing": ["<missing keywords>"],
  "flag": null,
  "flag_detail": ""
}}

Possible flags (use only when applicable):
- "LEGIBILITY_WARNING" — low legibility affected grading
- "BOUNDARY_CASE" — student is very close to gaining/losing marks"""

    async def _call_api():
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    try:
        if semaphore:
            async with semaphore:
                text = await _call_api()
        else:
            text = await _call_api()

        # Parse response
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        result = json.loads(text)

        # --- PHASE 2: Compare with teacher marks (if available) ---
        examiner_marks = student_ans.get("examiner_marks_written")
        if examiner_marks is not None:
            ai_marks = result.get("marks_awarded", 0)
            result["examiner_marks"] = examiner_marks
            result["ai_independent_marks"] = ai_marks

            if abs(ai_marks - examiner_marks) > 1:
                result["flag"] = "EXAMINER_DISCREPANCY"
                result["flag_detail"] = (
                    f"AI independently awarded {ai_marks}, teacher gave {examiner_marks}. "
                    f"Difference: {abs(ai_marks - examiner_marks)} marks."
                )

        # Post-process: MCQ/FIB force full or zero
        result = _post_process_mcq_fib(result, qtype, marks)

        result["attempted"] = True
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse evaluation for Q{qnum}: {e}")
        return _error_result(qnum, marks, f"JSON parse error: {e}")
    except openai.RateLimitError:
        raise  # Let the caller handle retry
    except Exception as e:
        logger.error(f"Evaluation failed for Q{qnum}: {e}")
        return _error_result(qnum, marks, str(e))


def _post_process_mcq_fib(result: dict, question_type: str, max_marks: float) -> dict:
    """For MCQ and FIB, force marks to full or zero (no partial)."""
    if question_type in ("MCQ", "FIB"):
        awarded = result.get("marks_awarded", 0)
        if awarded > 0 and awarded < max_marks:
            # If >= 50% threshold, give full marks; else zero
            if awarded >= (max_marks * 0.5):
                result["marks_awarded"] = max_marks
            else:
                result["marks_awarded"] = 0
    return result


def _error_result(question_number: str, max_marks: float, error_msg: str) -> dict:
    """Return an error result for a question that failed evaluation."""
    return {
        "question_number": question_number,
        "marks_awarded": 0,
        "marks_total": max_marks,
        "reasoning": f"Evaluation failed: {error_msg}",
        "student_feedback": "This question could not be evaluated automatically.",
        "keywords_matched": [],
        "keywords_missing": [],
        "flag": "MANUAL_REVIEW",
        "flag_detail": error_msg,
        "attempted": True,
    }


async def evaluate_all_questions(
    mapped_questions: List[dict],
    calibration_profile: dict,
    api_key: str,
    max_concurrent: int = 5,
) -> List[dict]:
    """
    Evaluate all attempted questions concurrently with rate limiting.
    Includes exponential backoff for rate limit errors.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []

    async def _evaluate_with_retry(mq: dict) -> dict:
        max_retries = 5
        base_delay = 2

        for attempt in range(max_retries):
            try:
                return await evaluate_question(mq, calibration_profile, api_key, semaphore)
            except openai.RateLimitError:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Rate limited on Q{mq['question_number']}, retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    return _error_result(
                        mq["question_number"],
                        mq.get("full_marks", mq.get("marks_allocated", 0)),
                        "Rate limit exceeded after max retries",
                    )

    tasks = [_evaluate_with_retry(mq) for mq in mapped_questions]
    results = await asyncio.gather(*tasks)

    return list(results)
