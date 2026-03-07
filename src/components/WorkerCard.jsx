import React from 'react';

export default function WorkerCard({ worker }) {
    const isOnline = worker.status === 'online';
    const isDead = worker.status === 'dead';

    return (
        <div
            className="card"
            style={{
                borderColor: isDead
                    ? 'rgba(248, 113, 113, 0.3)'
                    : isOnline
                        ? 'rgba(52, 211, 153, 0.15)'
                        : undefined,
            }}
        >
            <div className="card-header">
                <h3 className="card-title" style={{ fontSize: 15, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="4" y="4" width="16" height="16" rx="2" ry="2" />
                        <rect x="9" y="9" width="6" height="6" />
                    </svg>
                    {worker.worker_id}
                </h3>
                <span className={`badge ${isOnline ? 'badge-success' : isDead ? 'badge-danger' : 'badge-warning'}`}>
                    {worker.status}
                </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Host</span>
                    <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>{worker.host || '—'}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Threads</span>
                    <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>{worker.threads}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Jobs Processed</span>
                    <span style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{worker.jobs_processed || 0}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Last Heartbeat</span>
                    <span style={{ color: 'var(--text-secondary)', fontSize: 11.5 }}>
                        {worker.last_heartbeat ? new Date(worker.last_heartbeat).toLocaleTimeString() : '—'}
                    </span>
                </div>
            </div>
        </div>
    );
}
