"""
Mapper module — builds the Master Question Map and detects unattempted questions.
Cross-references student answers against the question paper.
Handles internal choice (OR) questions in Parts B and C.
"""

import re
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


def build_question_map(question_paper_ocr: dict) -> Dict[str, dict]:
    """
    Build a Master Question Map from the question paper OCR output.
    Returns a dict keyed by question_number with all question metadata.
    Handles internal choice sub-questions by preserving choice_group info.
    """
    qmap = {}
    questions = question_paper_ocr.get("questions", [])

    for q in questions:
        qnum = q.get("question_number", "")
        has_internal_choice = q.get("has_internal_choice", False)
        part = q.get("part", "")

        # For questions WITH internal choice, don't add the parent —
        # only add the sub-questions (the two OR options)
        if has_internal_choice and q.get("sub_questions"):
            for sq in q.get("sub_questions", []):
                sqnum = sq.get("question_number", "")
                if sqnum:
                    qmap[sqnum] = {
                        "question_number": sqnum,
                        "question_text": sq.get("question_text", ""),
                        "question_type": sq.get("question_type", "SHORT"),
                        "marks_allocated": sq.get("marks_allocated", q.get("marks_allocated", 0)),
                        "options": sq.get("options", []),
                        "special_instruction": sq.get("special_instruction"),
                        "choice_group": sq.get("choice_group", f"{qnum}_OR"),
                        "is_internal_choice": True,
                        "parent_question": qnum,
                        "part": part,
                    }
        else:
            # Regular question (Part A) or question without sub-questions
            if qnum:
                qmap[qnum] = {
                    "question_number": qnum,
                    "question_text": q.get("question_text", ""),
                    "question_type": q.get("question_type", "SHORT"),
                    "marks_allocated": q.get("marks_allocated", 0),
                    "options": q.get("options", []),
                    "special_instruction": q.get("special_instruction"),
                    "choice_group": None,
                    "is_internal_choice": False,
                    "parent_question": None,
                    "part": part,
                }

            # Also include non-choice sub-questions (if any)
            for sq in q.get("sub_questions", []):
                sqnum = sq.get("question_number", "")
                if sqnum and sq.get("special_instruction") != "INTERNAL_CHOICE":
                    qmap[sqnum] = {
                        "question_number": sqnum,
                        "question_text": sq.get("question_text", ""),
                        "question_type": sq.get("question_type", "SHORT"),
                        "marks_allocated": sq.get("marks_allocated", 0),
                        "options": sq.get("options", []),
                        "special_instruction": sq.get("special_instruction"),
                        "choice_group": None,
                        "is_internal_choice": False,
                        "parent_question": qnum,
                        "part": part,
                    }

    return qmap


def build_answer_key_map(answer_key_ocr: dict) -> Dict[str, dict]:
    """Build a lookup map from the answer key OCR output."""
    ak_map = {}
    for ans in answer_key_ocr.get("answers", []):
        qnum = ans.get("question_number", "")
        if qnum:
            ak_map[qnum] = ans
    return ak_map


def map_student_answers(
    question_map: Dict[str, dict],
    answer_key_map: Dict[str, dict],
    student_ocr: dict,
) -> List[dict]:
    """
    Map a student's answers against the question map.
    Returns a list of mapped questions with attempt status.
    
    For internal choice questions:
    - The student answers only ONE of the two OR options
    - The other option is marked as INTERNAL_CHOICE_SKIPPED (not penalized)
    """
    # Build student answer lookup
    student_answers = {}
    for ans in student_ocr.get("answers", []):
        qnum = ans.get("question_number", "")
        if qnum:
            student_answers[qnum] = ans

    # Track which choice groups the student has answered
    answered_choice_groups = {}
    for qnum, ans in student_answers.items():
        choice_group = ans.get("choice_group")
        if choice_group:
            answered_choice_groups[choice_group] = qnum

    mapped = []
    for qnum, qinfo in question_map.items():
        student_ans = student_answers.get(qnum)
        ak_info = answer_key_map.get(qnum, {})
        is_internal_choice = qinfo.get("is_internal_choice", False)
        choice_group = qinfo.get("choice_group")

        entry = {
            "question_number": qnum,
            "question_text": qinfo.get("question_text", ""),
            "question_type": qinfo.get("question_type", "SHORT"),
            "marks_allocated": qinfo.get("marks_allocated", 0),
            "special_instruction": qinfo.get("special_instruction"),
            "correct_answer": ak_info.get("correct_answer", ""),
            "acceptable_keywords": ak_info.get("acceptable_keywords", []),
            "marking_scheme": ak_info.get("marking_scheme", ""),
            "full_marks": ak_info.get("full_marks", qinfo.get("marks_allocated", 0)),
            "negative_marks": ak_info.get("negative_marks", 0),
            "step_marks": ak_info.get("step_marks", []),
            "is_internal_choice": is_internal_choice,
            "choice_group": choice_group,
            "part": qinfo.get("part", ""),
            "attempted": True,
            "flag": None,
        }

        if student_ans is None:
            # Not found in student sheet
            if is_internal_choice and choice_group:
                # Check if the student answered the OTHER option in this choice group
                answered_qnum = answered_choice_groups.get(choice_group)
                if answered_qnum and answered_qnum != qnum:
                    # Student chose the other option — this is a valid skip
                    entry["attempted"] = False
                    entry["flag"] = "INTERNAL_CHOICE_SKIPPED"
                    entry["student_answer"] = {}
                else:
                    # Student didn't answer either option — genuinely unattempted
                    entry["attempted"] = False
                    entry["flag"] = "UNATTEMPTED"
                    entry["student_answer"] = {}
            else:
                # Regular question not found
                entry["attempted"] = False
                entry["flag"] = "UNATTEMPTED"
                entry["student_answer"] = {}
        elif student_ans.get("is_blank", False):
            entry["attempted"] = False
            entry["flag"] = "UNATTEMPTED"
            entry["student_answer"] = student_ans
        elif student_ans.get("is_crossed_out", False):
            entry["attempted"] = False
            entry["flag"] = "UNATTEMPTED"
            entry["student_answer"] = student_ans
        else:
            entry["student_answer"] = student_ans

        mapped.append(entry)

    return mapped


def handle_optional_sections(
    mapped_questions: List[dict],
) -> List[dict]:
    """
    Handle optional sections and internal choices.
    
    1. Internal Choice (OR): Questions flagged as INTERNAL_CHOICE_SKIPPED
       are valid skips — the student chose the other option. These should
       NOT be penalized and should NOT count toward total marks.
    
    2. Attempt any N of M: Evaluate all but only count the best N.
    """
    # Group questions by special_instruction for "attempt any N" type
    optional_groups: Dict[str, List[dict]] = {}

    for mq in mapped_questions:
        instruction = mq.get("special_instruction")
        if instruction and "attempt any" in (instruction or "").lower():
            key = instruction.lower()
            if key not in optional_groups:
                optional_groups[key] = []
            optional_groups[key].append(mq)

    # Tag optional group questions
    for key, group in optional_groups.items():
        for mq in group:
            mq["optional_group"] = key

    return mapped_questions


def get_unattempted_questions(mapped_questions: List[dict]) -> List[str]:
    """Return list of genuinely unattempted question numbers.
    Excludes INTERNAL_CHOICE_SKIPPED (those are valid skips)."""
    return [
        mq["question_number"]
        for mq in mapped_questions
        if not mq.get("attempted", True) and mq.get("flag") != "INTERNAL_CHOICE_SKIPPED"
    ]


def apply_optional_counting(
    evaluated_questions: List[dict],
) -> List[dict]:
    """
    After evaluation:
    1. For internal choice (OR) questions: mark the SKIPPED option as
       INTERNAL_CHOICE_SKIPPED so it doesn't count in totals.
    2. For 'attempt any N of M': keep the best N and mark rest as OPTIONAL_NOT_COUNTED.
    """
    # --- Handle Internal Choice ---
    # Questions flagged INTERNAL_CHOICE_SKIPPED should not count toward totals
    for eq in evaluated_questions:
        if eq.get("flag") == "INTERNAL_CHOICE_SKIPPED":
            eq["marks_awarded"] = 0
            eq["marks_total"] = 0  # Don't count in total possible either
            eq["reasoning"] = "Student chose the other option (internal choice)."
            eq["student_feedback"] = "You attempted the other option for this question."

    # --- Handle Optional Groups (attempt any N of M) ---
    optional_groups: Dict[str, List[dict]] = {}
    for eq in evaluated_questions:
        group = eq.get("optional_group")
        if group:
            if group not in optional_groups:
                optional_groups[group] = []
            optional_groups[group].append(eq)

    for key, group in optional_groups.items():
        # Parse "attempt any N of M"
        match = re.search(r"attempt any (\d+)", key)
        if match:
            n = int(match.group(1))
            # Sort by marks_awarded descending
            attempted = [q for q in group if q.get("attempted", True)]
            attempted.sort(key=lambda x: x.get("marks_awarded", 0), reverse=True)

            # Keep top N, mark rest as not counted
            for i, q in enumerate(attempted):
                if i >= n:
                    q["flag"] = "OPTIONAL_NOT_COUNTED"
                    q["marks_awarded"] = 0

    return evaluated_questions
