import React from 'react';

export default function ResultsTable({ students, onSelect }) {
    if (!students || students.length === 0) {
        return <div style={{ color: 'var(--text-muted)', padding: 20 }}>No results available.</div>;
    }

    return (
        <div className="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Roll No</th>
                        <th>Marks</th>
                        <th>%</th>
                        <th>Grade</th>
                        <th>Unattempted</th>
                        <th>Flags</th>
                    </tr>
                </thead>
                <tbody>
                    {students.map((s) => (
                        <tr
                            key={s.roll_number}
                            className="expandable"
                            onClick={() => onSelect?.(s)}
                        >
                            <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{s.roll_number}</td>
                            <td>{s.total_marks_awarded}/{s.total_marks_possible}</td>
                            <td>{s.percentage}%</td>
                            <td>
                                <span className={`badge ${s.grade === 'F' ? 'badge-danger' : 'badge-success'}`}>
                                    {s.grade}
                                </span>
                            </td>
                            <td style={{ fontSize: 12 }}>{(s.unattempted_questions || []).join(', ') || '—'}</td>
                            <td>
                                {(s.flagged_questions || []).length > 0 && (
                                    <span className="badge badge-warning">{s.flagged_questions.length}</span>
                                )}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
