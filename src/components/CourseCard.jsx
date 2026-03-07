import React from 'react';

export default function CourseCard({ course }) {
    const hasQP = !!course.file_inventory?.question_paper;
    const hasAK = !!course.file_inventory?.answer_key;
    const studentCount = course.student_count || 0;
    const isIncomplete = course.status === 'INCOMPLETE';

    return (
        <div
            className="card"
            style={{
                borderColor: isIncomplete ? 'rgba(248, 113, 113, 0.3)' : undefined,
            }}
        >
            <div className="card-header">
                <h3 className="card-title" style={{ fontSize: 18 }}>{course.course_code}</h3>
                <span className={`badge ${isIncomplete ? 'badge-danger' : 'badge-success'}`}>
                    {isIncomplete ? 'INCOMPLETE' : 'READY'}
                </span>
            </div>

            <div style={{ display: 'flex', gap: 16, marginBottom: 12 }}>
                <div className="status-indicator">
                    <span className={`dot ${hasQP ? 'success' : 'error'}`} />
                    <span style={{ fontSize: 12.5, color: 'var(--text-secondary)' }}>QP {hasQP ? '✓' : '✗'}</span>
                </div>
                <div className="status-indicator">
                    <span className={`dot ${hasAK ? 'success' : 'error'}`} />
                    <span style={{ fontSize: 12.5, color: 'var(--text-secondary)' }}>AK {hasAK ? '✓' : '✗'}</span>
                </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                    <circle cx="9" cy="7" r="4" />
                    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
                <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                    {studentCount} student{studentCount !== 1 ? 's' : ''}
                </span>
            </div>

            {course.error && (
                <div style={{ marginTop: 12, padding: '8px 10px', background: 'rgba(248,113,113,0.06)', borderRadius: 6, fontSize: 11.5, color: 'var(--accent-red)' }}>
                    {course.error}
                </div>
            )}
        </div>
    );
}
