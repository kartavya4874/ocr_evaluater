import React from 'react';
import FlagBadge from './FlagBadge';

export default function QuestionBreakdown({ questions }) {
    if (!questions || questions.length === 0) {
        return <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No question data available.</div>;
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h4 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                Question Breakdown
            </h4>
            {questions.map((q, i) => (
                <div
                    key={i}
                    style={{
                        padding: '12px 16px',
                        background: 'var(--bg-glass)',
                        borderRadius: 8,
                        borderLeft: `3px solid ${!q.attempted ? 'var(--accent-amber)' :
                                q.marks_awarded >= q.marks_total ? 'var(--accent-emerald)' :
                                    q.marks_awarded === 0 ? 'var(--accent-red)' :
                                        'var(--accent-indigo)'
                            }`,
                    }}
                >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)' }}>
                                Q{q.question_number}
                            </span>
                            {q.question_type && (
                                <span className="badge badge-purple" style={{ fontSize: 10 }}>{q.question_type}</span>
                            )}
                            {q.flag && <FlagBadge flag={q.flag} detail={q.flag_detail} />}
                        </div>
                        <span style={{ fontWeight: 700, fontSize: 15, color: 'var(--text-primary)' }}>
                            {q.marks_awarded ?? 0}
                            <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}> / {q.marks_total || 0}</span>
                        </span>
                    </div>

                    {q.reasoning && (
                        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6, lineHeight: 1.6 }}>
                            <strong>Reasoning:</strong> {q.reasoning}
                        </div>
                    )}

                    {q.student_feedback && (
                        <div style={{ fontSize: 12, color: 'var(--accent-cyan)', marginBottom: 6, lineHeight: 1.6 }}>
                            <strong>Feedback:</strong> {q.student_feedback}
                        </div>
                    )}

                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {(q.keywords_matched || []).map((kw, j) => (
                            <span key={`m-${j}`} className="chip chip-keyword">✓ {kw}</span>
                        ))}
                        {(q.keywords_missing || []).map((kw, j) => (
                            <span key={`x-${j}`} className="chip chip-missing">✗ {kw}</span>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}
