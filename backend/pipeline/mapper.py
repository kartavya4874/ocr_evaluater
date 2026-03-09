"""
Mapper module — builds the Master Question Map and detects unattempted questions.
Cross-references student answers against the question paper.
Handles OR/alternative questions (e.g., 11.1 OR 11.2).
"""

import logging
import re
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


def build_question_map(question_paper_ocr: dict) -> Dict[str, dict]:
    """
    Build a Master Question Map from the question paper OCR output.
    Returns a dict keyed by question_number with all question metadata.
    Preserves or_group info for OR/alternative questions.
    """
    qmap = {}
    questions = question_paper_ocr.get("questions", [])

    for q in questions:
        qnum = q.get("question_number", "")
        if qnum:
            qmap[qnum] = {
                "question_number": qnum,
                "question_text": q.get("question_text", ""),
                "question_type": q.get("question_type", "SHORT"),
                "marks_allocated": q.get("marks_allocated", 0),
                "options": q.get("options", []),
                "special_instruction": q.get("special_instruction"),
                "or_group": _normalize_or_group(q.get("or_group")),
            }

        # Also include sub-questions
        for sq in q.get("sub_questions", []):
            sqnum = sq.get("question_number", "")
            if sqnum:
                qmap[sqnum] = {
                    "question_number": sqnum,
                    "question_text": sq.get("question_text", ""),
                    "question_type": sq.get("question_type", "SHORT"),
                    "marks_allocated": sq.get("marks_allocated", 0),
                    "options": sq.get("options", []),
                    "special_instruction": sq.get("special_instruction"),
                    "or_group": _normalize_or_group(sq.get("or_group")) or _normalize_or_group(q.get("or_group")),
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


def _normalize_or_group(value) -> Optional[str]:
    """Normalize or_group values — treat empty/null/None as no group."""
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("", "null", "none", "n/a"):
            return None
        return value.strip()
    return str(value)


def _resolve_or_groups(
    question_map: Dict[str, dict],
    student_answers: Dict[str, dict],
) -> Dict[str, str]:
    """
    For OR/alternative question groups, determine which alternative was attempted.
    Returns a dict mapping question_number -> flag for un-chosen alternatives.
    Questions that were NOT chosen get 'OR_NOT_CHOSEN'.
    """
    or_flags: Dict[str, str] = {}

    # Group questions by or_group
    or_groups: Dict[str, List[str]] = {}
    for qnum, qinfo in question_map.items():
        group = _normalize_or_group(qinfo.get("or_group"))
        if group:
            if group not in or_groups:
                or_groups[group] = []
            or_groups[group].append(qnum)

    logger.debug(f"OR groups detected: {or_groups}")

    for group, qnums in or_groups.items():
        if len(qnums) < 2:
            continue  # Not really an OR group

        # Check which alternatives were attempted
        attempted = []
        unattempted = []
        for qnum in qnums:
            sa = student_answers.get(qnum)
            if sa and not sa.get("is_blank", False) and not sa.get("is_crossed_out", False):
                attempted.append(qnum)
            else:
                unattempted.append(qnum)

        logger.debug(f"OR group '{group}': attempted={attempted}, unattempted={unattempted}")

        if attempted:
            # Student attempted at least one — mark others as OR_NOT_CHOSEN
            for qnum in qnums:
                if qnum not in attempted:
                    or_flags[qnum] = "OR_NOT_CHOSEN"
        else:
            # None attempted — pick the first as the "active" one, rest as OR_NOT_CHOSEN
            # This way total_possible still counts the group once
            for qnum in qnums[1:]:
                or_flags[qnum] = "OR_NOT_CHOSEN"

    return or_flags


def map_student_answers(
    question_map: Dict[str, dict],
    answer_key_map: Dict[str, dict],
    student_ocr: dict,
) -> List[dict]:
    """
    Map a student's answers against the question map.
    Returns a list of mapped questions with attempt status.
    Handles OR/alternative questions by marking un-chosen alternatives.
    """
    # Build student answer lookup
    student_answers = {}
    for ans in student_ocr.get("answers", []):
        qnum = ans.get("question_number", "")
        if qnum:
            student_answers[qnum] = ans

    # Debug: log the question numbers for matching analysis
    qmap_keys = set(question_map.keys())
    sa_keys = set(student_answers.keys())
    logger.info(f"Question map keys: {sorted(qmap_keys)}")
    logger.info(f"Student answer keys: {sorted(sa_keys)}")
    logger.info(f"Matched keys: {sorted(qmap_keys & sa_keys)}")
    logger.info(f"In QP but not student: {sorted(qmap_keys - sa_keys)}")
    logger.info(f"In student but not QP: {sorted(sa_keys - qmap_keys)}")

    # Resolve OR groups
    or_flags = _resolve_or_groups(question_map, student_answers)

    mapped = []
    for qnum, qinfo in question_map.items():
        student_ans = student_answers.get(qnum)
        ak_info = answer_key_map.get(qnum, {})

        entry = {
            "question_number": qnum,
            "question_text": qinfo.get("question_text", ""),
            "question_type": qinfo.get("question_type", "SHORT"),
            "marks_allocated": qinfo.get("marks_allocated", 0),
            "special_instruction": qinfo.get("special_instruction"),
            "or_group": _normalize_or_group(qinfo.get("or_group")),
            "correct_answer": ak_info.get("correct_answer", ""),
            "acceptable_keywords": ak_info.get("acceptable_keywords", []),
            "marking_scheme": ak_info.get("marking_scheme", ""),
            "full_marks": ak_info.get("full_marks", qinfo.get("marks_allocated", 0)),
            "negative_marks": ak_info.get("negative_marks", 0),
            "step_marks": ak_info.get("step_marks", []),
            "attempted": True,
            "flag": None,
        }

        # Check if this is an OR alternative that was NOT chosen
        if qnum in or_flags:
            entry["attempted"] = False
            entry["flag"] = "OR_NOT_CHOSEN"
            entry["student_answer"] = {}
        elif student_ans is None:
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
    Handle optional sections ('attempt any N of M').
    For optional groups, evaluate all but only count the best N.
    """
    # Group questions by special_instruction
    optional_groups: Dict[str, List[dict]] = {}

    for mq in mapped_questions:
        instruction = mq.get("special_instruction")
        if instruction and "attempt any" in (instruction or "").lower():
            key = instruction.lower()
            if key not in optional_groups:
                optional_groups[key] = []
            optional_groups[key].append(mq)

    # For each optional group, we'll mark excess as OPTIONAL_NOT_COUNTED after evaluation
    # For now, just tag them
    for key, group in optional_groups.items():
        for mq in group:
            mq["optional_group"] = key

    return mapped_questions


def get_unattempted_questions(mapped_questions: List[dict]) -> List[str]:
    """Return list of unattempted question numbers."""
    return [
        mq["question_number"]
        for mq in mapped_questions
        if not mq.get("attempted", True)
    ]


def apply_optional_counting(
    evaluated_questions: List[dict],
) -> List[dict]:
    """
    After evaluation, for optional groups, keep the best N and mark the rest as OPTIONAL_NOT_COUNTED.
    """
    # Group by optional_group
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
