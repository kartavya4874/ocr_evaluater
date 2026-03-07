import React, { useState, useEffect } from 'react';
import { getResults, getResultsByCourse } from '../lib/api';
import ResultsTable from '../components/ResultsTable';
import QuestionBreakdown from '../components/QuestionBreakdown';
import FlagBadge from '../components/FlagBadge';

export default function Results() {
    const [courses, setCourses] = useState([]);
    const [selectedCourse, setSelectedCourse] = useState(null);
    const [students, setStudents] = useState([]);
    const [expandedRoll, setExpandedRoll] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        getResults()
            .then((data) => {
                setCourses(data.courses || []);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    async function handleSelectCourse(courseCode) {
        setSelectedCourse(courseCode);
        setExpandedRoll(null);
        try {
            const data = await getResultsByCourse(courseCode);
            setStudents(data.students || []);
        } catch (err) {
            alert('Failed to load results: ' + err.message);
        }
    }

    if (loading) {
        return (
            <div className="empty-state">
                <div className="spinner spinner-lg"></div>
                <p style={{ marginTop: 16 }}>Loading results...</p>
            </div>
        );
    }

    return (
        <div className="fade-in">
            <div className="page-header">
                <h2>Results</h2>
                <p>Browse evaluation results by course and student</p>
            </div>

            <div style={{ display: 'flex', gap: 24 }}>
                {/* Course Sidebar */}
                <div style={{ width: 240, flexShrink: 0 }}>
                    <h4 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--text-muted)', marginBottom: 10, fontWeight: 700 }}>
                        Courses
                    </h4>
                    {courses.length === 0 ? (
                        <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No results available</div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                            {courses.map((course) => (
                                <div
                                    key={course.course_code}
                                    id={`course-${course.course_code}`}
                                    className={`nav-item ${selectedCourse === course.course_code ? 'active' : ''}`}
                                    onClick={() => handleSelectCourse(course.course_code)}
                                    style={{ padding: '10px 12px' }}
                                >
                                    <div style={{ flex: 1 }}>
                                        <div style={{ fontWeight: 600, fontSize: 13.5 }}>{course.course_code}</div>
                                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                                            {course.student_count} students · Avg {course.avg_percentage}%
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Student list / Results */}
                <div style={{ flex: 1 }}>
                    {!selectedCourse ? (
                        <div className="empty-state">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                                <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                            </svg>
                            <h3>Select a course</h3>
                            <p>Choose a course from the sidebar to view student results</p>
                        </div>
                    ) : (
                        <>
                            <h3 style={{ fontSize: 20, fontWeight: 600, marginBottom: 16 }}>
                                {selectedCourse}
                                <span style={{ fontSize: 14, color: 'var(--text-muted)', fontWeight: 400, marginLeft: 12 }}>
                                    {students.length} students
                                </span>
                            </h3>

                            <div className="table-container">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Roll Number</th>
                                            <th>Marks</th>
                                            <th>Percentage</th>
                                            <th>Grade</th>
                                            <th>Flags</th>
                                            <th></th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {students.map((student) => (
                                            <React.Fragment key={student.roll_number}>
                                                <tr
                                                    className="expandable"
                                                    onClick={() =>
                                                        setExpandedRoll(
                                                            expandedRoll === student.roll_number ? null : student.roll_number
                                                        )
                                                    }
                                                    style={{
                                                        background: expandedRoll === student.roll_number
                                                            ? 'rgba(129, 140, 248, 0.06)'
                                                            : undefined,
                                                    }}
                                                >
                                                    <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                                                        {student.roll_number}
                                                    </td>
                                                    <td>
                                                        {student.total_marks_awarded} / {student.total_marks_possible}
                                                    </td>
                                                    <td>
                                                        <div className="progress-bar" style={{ width: 100, display: 'inline-block', marginRight: 8 }}>
                                                            <div
                                                                className="fill"
                                                                style={{
                                                                    width: `${Math.min(student.percentage, 100)}%`,
                                                                    background: student.percentage >= 70
                                                                        ? 'var(--gradient-success)'
                                                                        : student.percentage >= 40
                                                                            ? 'var(--gradient-primary)'
                                                                            : 'var(--gradient-danger)',
                                                                }}
                                                            />
                                                        </div>
                                                        {student.percentage}%
                                                    </td>
                                                    <td>
                                                        <span className={`badge ${student.grade === 'F' ? 'badge-danger' :
                                                                ['O', 'A+', 'A'].includes(student.grade) ? 'badge-success' :
                                                                    'badge-info'
                                                            }`}>
                                                            {student.grade}
                                                        </span>
                                                    </td>
                                                    <td>
                                                        {student.flagged_questions?.map((f, i) => (
                                                            <FlagBadge key={i} flag={f.flag} detail={f.flag_detail} />
                                                        ))}
                                                    </td>
                                                    <td style={{ color: 'var(--text-muted)' }}>
                                                        {expandedRoll === student.roll_number ? '▲' : '▼'}
                                                    </td>
                                                </tr>

                                                {expandedRoll === student.roll_number && (
                                                    <tr>
                                                        <td colSpan="6" style={{ padding: 0, border: 'none' }}>
                                                            <div className="expanded-content">
                                                                {/* Overall Feedback */}
                                                                {student.overall_feedback && (
                                                                    <div
                                                                        style={{
                                                                            padding: '12px 16px',
                                                                            background: 'rgba(129, 140, 248, 0.06)',
                                                                            borderRadius: 8,
                                                                            marginBottom: 16,
                                                                            fontSize: 13,
                                                                            lineHeight: 1.7,
                                                                            color: 'var(--text-secondary)',
                                                                        }}
                                                                    >
                                                                        <strong style={{ color: 'var(--text-primary)' }}>Overall Feedback:</strong>{' '}
                                                                        {student.overall_feedback}
                                                                    </div>
                                                                )}

                                                                {/* Question Breakdown */}
                                                                <QuestionBreakdown questions={student.question_breakdown || []} />
                                                            </div>
                                                        </td>
                                                    </tr>
                                                )}
                                            </React.Fragment>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
