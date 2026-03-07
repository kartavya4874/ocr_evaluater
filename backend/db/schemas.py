"""
Pydantic models for the Exam Evaluator backend.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# --- Enums ---

class QuestionType(str, Enum):
    MCQ = "MCQ"
    FIB = "FIB"
    SHORT = "SHORT"
    LONG = "LONG"
    DIAGRAM = "DIAGRAM"
    CODE = "CODE"
    MATH = "MATH"
    CHEMISTRY = "CHEMISTRY"
    NUMERICAL = "NUMERICAL"


class Legibility(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    OCR_DONE = "OCR_DONE"
    EVALUATING = "EVALUATING"
    EVALUATED = "EVALUATED"
    SAVED = "SAVED"
    FAILED = "FAILED"


class CourseStatus(str, Enum):
    READY = "READY"
    INCOMPLETE = "INCOMPLETE"
    EVALUATING = "EVALUATING"
    DONE = "DONE"


# --- Question Paper OCR ---

class SubQuestion(BaseModel):
    question_number: str
    question_text: str
    question_type: str = "SHORT"
    marks_allocated: float = 0
    options: List[str] = []
    special_instruction: Optional[str] = None


class QuestionItem(BaseModel):
    question_number: str
    question_text: str
    question_type: str = "SHORT"
    marks_allocated: float = 0
    options: List[str] = []
    sub_questions: List[SubQuestion] = []
    special_instruction: Optional[str] = None


class QuestionPaperOCR(BaseModel):
    total_marks: float = 100
    questions: List[QuestionItem] = []


# --- Answer Key OCR ---

class StepMark(BaseModel):
    step: str
    marks: float


class AnswerKeyItem(BaseModel):
    question_number: str
    correct_answer: str = ""
    acceptable_keywords: List[str] = []
    marking_scheme: str = ""
    full_marks: float = 0
    negative_marks: float = 0
    step_marks: List[StepMark] = []


class AnswerKeyOCR(BaseModel):
    answers: List[AnswerKeyItem] = []


# --- Answer Sheet OCR ---

class StudentAnswerItem(BaseModel):
    question_number: str
    answer_text: str = ""
    diagram_description: str = ""
    code_written: str = ""
    math_expression: str = ""
    chemistry_notation: str = ""
    is_blank: bool = False
    is_crossed_out: bool = False
    legibility: str = "HIGH"
    examiner_marks_written: Optional[float] = None


class AnswerSheetOCR(BaseModel):
    roll_number: str = ""
    answers: List[StudentAnswerItem] = []


# --- Evaluation Result ---

class QuestionEvaluation(BaseModel):
    question_number: str
    marks_awarded: float = 0
    marks_total: float = 0
    reasoning: str = ""
    student_feedback: str = ""
    keywords_matched: List[str] = []
    keywords_missing: List[str] = []
    flag: Optional[str] = None
    flag_detail: Optional[str] = None
    attempted: bool = True


class EvaluationResult(BaseModel):
    roll_number: str
    course_code: str
    total_marks_awarded: float = 0
    total_marks_possible: float = 0
    percentage: float = 0.0
    grade: str = ""
    question_breakdown: List[QuestionEvaluation] = []
    unattempted_questions: List[str] = []
    flagged_questions: List[Dict[str, Any]] = []
    overall_feedback: str = ""
    evaluated_at: str = ""
    model_used: str = "claude-opus-4-6"


# --- Course Data ---

class CourseData(BaseModel):
    course_code: str
    question_map: Dict[str, Any] = {}
    calibration_profile: Dict[str, Any] = {}
    total_marks: float = 100
    last_updated: str = ""


# --- Job Log ---

class JobLog(BaseModel):
    job_id: str
    course_code: str
    roll_number: str
    status: str = "QUEUED"
    error: Optional[str] = None
    retries: int = 0
    node_id: str = "local"
    updated_at: str = ""


# --- Worker Info ---

class WorkerInfo(BaseModel):
    worker_id: str
    host: str = ""
    threads: int = 1
    status: str = "online"
    jobs_processed: int = 0
    last_heartbeat: str = ""


# --- Config ---

class ConfigModel(BaseModel):
    root_exam_folder: str = ""
    export_output_folder: str = ""
    anthropic_api_key: str = ""
    mongodb_uri: str = "mongodb://localhost:27017"
    redis_url: str = "redis://localhost:6379"
    distributed_mode: bool = False
    head_node_port: int = 8765
    re_evaluate: bool = False
    max_concurrent_api_calls: int = 5
    grading_scale: Dict[str, float] = {
        "O": 90, "A+": 80, "A": 70,
        "B+": 60, "B": 50, "C": 40, "F": 0
    }
    selected_courses: str = "ALL"


# --- Scan Result ---

class FileInventory(BaseModel):
    question_paper: Optional[str] = None
    answer_key: Optional[str] = None
    student_sheets: List[Dict[str, str]] = []  # [{roll_number, file_path}]


class CourseScanResult(BaseModel):
    course_code: str
    status: str = "READY"
    file_inventory: FileInventory = Field(default_factory=FileInventory)
    student_count: int = 0
    error: Optional[str] = None


class ScanResult(BaseModel):
    courses: List[CourseScanResult] = []
    total_students: int = 0
    total_courses: int = 0
    incomplete_courses: List[str] = []


# --- SSE Progress Event ---

class ProgressEvent(BaseModel):
    job_id: str = ""
    course_code: str = ""
    roll_number: str = ""
    stage: str = ""
    marks: Optional[float] = None
    total: Optional[float] = None
    message: str = ""
    flag: Optional[str] = None
