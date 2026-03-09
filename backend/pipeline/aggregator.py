"""
Aggregator module — sums marks, computes grades, and generates overall feedback.
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from openai import OpenAI

logger = logging.getLogger(__name__)


def compute_total_marks(evaluated_questions: List[dict]) -> tuple:
    """
    Sum up marks from evaluated questions.
    Returns (total_awarded, total_possible).
    """
    total_awarded = 0.0
    total_possible = 0.0

    for eq in evaluated_questions:
        # Skip questions flagged as OPTIONAL_NOT_COUNTED
        if eq.get("flag") == "OPTIONAL_NOT_COUNTED":
            continue

        total_awarded += eq.get("marks_awarded", 0)
        total_possible += eq.get("marks_total", 0)

    return total_awarded, total_possible


def compute_percentage(total_awarded: float, total_possible: float) -> float:
    """Compute percentage, handling division by zero."""
    if total_possible == 0:
        return 0.0
    return round((total_awarded / total_possible) * 100, 2)


def compute_grade(percentage: float, grading_scale: Dict[str, float]) -> str:
    """
    Compute grade based on percentage and grading scale.
    Grading scale is {grade: minimum_percentage}.
    """
    # Sort by minimum percentage descending
    sorted_grades = sorted(grading_scale.items(), key=lambda x: x[1], reverse=True)

    for grade, min_pct in sorted_grades:
        if percentage >= min_pct:
            return grade

    return "F"


def get_flagged_questions(evaluated_questions: List[dict]) -> List[dict]:
    """Extract questions with flags."""
    flagged = []
    for eq in evaluated_questions:
        if eq.get("flag") and eq["flag"] not in ("UNATTEMPTED", "OPTIONAL_NOT_COUNTED"):
            flagged.append({
                "question_number": eq["question_number"],
                "flag": eq["flag"],
                "flag_detail": eq.get("flag_detail", ""),
                "marks_awarded": eq.get("marks_awarded", 0),
                "marks_total": eq.get("marks_total", 0),
            })
    return flagged


def get_unattempted_list(evaluated_questions: List[dict]) -> List[str]:
    """Get list of unattempted question numbers."""
    return [
        eq["question_number"]
        for eq in evaluated_questions
        if not eq.get("attempted", True) or eq.get("flag") == "UNATTEMPTED"
    ]


async def generate_overall_feedback(
    roll_number: str,
    course_code: str,
    evaluated_questions: List[dict],
    total_awarded: float,
    total_possible: float,
    percentage: float,
    grade: str,
    api_key: str,
) -> str:
    """Generate an overall feedback paragraph using GPT-4o."""
    # Build summary for the model
    question_summaries = []
    for eq in evaluated_questions:
        q_summary = f"Q{eq['question_number']}: {eq.get('marks_awarded', 0)}/{eq.get('marks_total', 0)}"
        if not eq.get("attempted", True):
            q_summary += " (not attempted)"
        elif eq.get("flag"):
            q_summary += f" [{eq['flag']}]"
        question_summaries.append(q_summary)

    prompt = f"""Write a brief, constructive overall feedback paragraph for a student's exam performance.

Student: {roll_number}
Course: {course_code}
Total: {total_awarded}/{total_possible} ({percentage}%)
Grade: {grade}

Question-wise breakdown:
{chr(10).join(question_summaries)}

Write 3-5 sentences covering:
1. Overall performance assessment
2. Strongest areas
3. Areas needing improvement
4. Specific advice for improvement

Return ONLY the feedback paragraph text. No JSON, no formatting, just the text."""

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Failed to generate feedback for {roll_number}: {e}")
        return f"Overall score: {total_awarded}/{total_possible} ({percentage}%), Grade: {grade}."


async def aggregate_student_result(
    roll_number: str,
    course_code: str,
    evaluated_questions: List[dict],
    grading_scale: Dict[str, float],
    api_key: str,
) -> dict:
    """
    Aggregate all question evaluations into a final student result.
    """
    total_awarded, total_possible = compute_total_marks(evaluated_questions)
    percentage = compute_percentage(total_awarded, total_possible)
    grade = compute_grade(percentage, grading_scale)
    flagged = get_flagged_questions(evaluated_questions)
    unattempted = get_unattempted_list(evaluated_questions)

    # Generate overall feedback
    feedback = await generate_overall_feedback(
        roll_number, course_code, evaluated_questions,
        total_awarded, total_possible, percentage, grade, api_key,
    )

    return {
        "roll_number": roll_number,
        "course_code": course_code,
        "total_marks_awarded": total_awarded,
        "total_marks_possible": total_possible,
        "percentage": percentage,
        "grade": grade,
        "question_breakdown": evaluated_questions,
        "unattempted_questions": unattempted,
        "flagged_questions": flagged,
        "overall_feedback": feedback,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "model_used": "gpt-4o",
    }
