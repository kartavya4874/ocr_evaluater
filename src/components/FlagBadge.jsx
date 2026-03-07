import React from 'react';

const FLAG_STYLES = {
    UNATTEMPTED: { bg: 'rgba(251,191,36,0.15)', color: 'var(--accent-amber)', label: 'Unattempted' },
    LEGIBILITY_WARNING: { bg: 'rgba(248,113,113,0.15)', color: 'var(--accent-red)', label: 'Legibility' },
    EXAMINER_DISCREPANCY: { bg: 'rgba(192,132,252,0.15)', color: 'var(--accent-purple)', label: 'Discrepancy' },
    BOUNDARY_CASE: { bg: 'rgba(96,165,250,0.15)', color: 'var(--accent-blue)', label: 'Boundary' },
    MANUAL_REVIEW: { bg: 'rgba(248,113,113,0.15)', color: 'var(--accent-red)', label: 'Review' },
    OPTIONAL_NOT_COUNTED: { bg: 'rgba(100,116,139,0.15)', color: 'var(--text-muted)', label: 'Not Counted' },
    ROLL_FROM_FILENAME: { bg: 'rgba(251,191,36,0.15)', color: 'var(--accent-amber)', label: 'Roll guess' },
};

export default function FlagBadge({ flag, detail }) {
    if (!flag) return null;

    const style = FLAG_STYLES[flag] || { bg: 'rgba(100,116,139,0.15)', color: 'var(--text-muted)', label: flag };

    return (
        <span
            title={detail || flag}
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '2px 8px',
                borderRadius: 4,
                fontSize: 10.5,
                fontWeight: 700,
                background: style.bg,
                color: style.color,
                cursor: detail ? 'help' : 'default',
            }}
        >
            ⚑ {style.label}
        </span>
    );
}
