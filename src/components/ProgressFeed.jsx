import React from 'react';

export default function ProgressFeed({ events }) {
    function getStageClass(stage) {
        if (stage.includes('OCR')) return 'ocr';
        if (stage === 'EVALUATING') return 'evaluating';
        if (stage === 'SAVED') return 'saved';
        if (stage === 'FAILED') return 'failed';
        if (stage === 'SCANNING' || stage === 'SCAN_DONE') return 'scanning';
        return '';
    }

    function getStageIcon(stage) {
        if (stage.includes('OCR')) return '📷';
        if (stage === 'EVALUATING') return '⚡';
        if (stage === 'SAVED') return '✅';
        if (stage === 'FAILED') return '❌';
        if (stage === 'SCANNING' || stage === 'SCAN_DONE') return '🔍';
        if (stage === 'COMPLETE') return '🎉';
        if (stage === 'CANCELLED') return '⏹';
        if (stage === 'CALIBRATING') return '📐';
        if (stage === 'SKIPPED') return '⏭';
        return '📋';
    }

    return (
        <div className="progress-feed">
            {events.map((evt, i) => (
                <div key={i} className={`progress-item ${getStageClass(evt.stage)}`}>
                    <span style={{ fontSize: 16, display: 'inline-flex', flexShrink: 0 }}>{getStageIcon(evt.stage)}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            {evt.course_code && (
                                <span className="badge badge-purple" style={{ fontSize: 10 }}>{evt.course_code}</span>
                            )}
                            {evt.roll_number && (
                                <span style={{ fontWeight: 600, fontSize: 12, color: 'var(--text-primary)' }}>{evt.roll_number}</span>
                            )}
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {evt.message}
                        </div>
                    </div>
                    {evt.marks !== null && evt.marks !== undefined && (
                        <span className="badge badge-success" style={{ flexShrink: 0 }}>
                            {evt.marks}/{evt.total}
                        </span>
                    )}
                    {evt.flag && (
                        <span className="badge badge-warning" style={{ flexShrink: 0 }}>
                            {evt.flag}
                        </span>
                    )}
                </div>
            ))}
        </div>
    );
}
