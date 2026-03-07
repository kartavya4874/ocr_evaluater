import React, { useState, useEffect, useRef } from 'react';
import { scanFolder, startEvaluation, stopEvaluation, subscribeProgress } from '../lib/api';
import CourseCard from '../components/CourseCard';
import ProgressFeed from '../components/ProgressFeed';

export default function Dashboard() {
    const [scanResult, setScanResult] = useState(null);
    const [scanning, setScanning] = useState(false);
    const [evaluating, setEvaluating] = useState(false);
    const [events, setEvents] = useState([]);
    const [stats, setStats] = useState({ total: 0, evaluated: 0, inProgress: 0, failed: 0, flagged: 0 });
    const eventSourceRef = useRef(null);

    async function handleScan() {
        setScanning(true);
        try {
            const result = await scanFolder();
            setScanResult(result);
        } catch (err) {
            alert('Scan failed: ' + err.message);
        }
        setScanning(false);
    }

    async function handleStart() {
        setEvaluating(true);
        setEvents([]);
        setStats({ total: 0, evaluated: 0, inProgress: 0, failed: 0, flagged: 0 });

        try {
            await startEvaluation();

            // Subscribe to SSE
            const es = subscribeProgress((event) => {
                setEvents((prev) => [event, ...prev].slice(0, 500));

                setStats((prev) => {
                    const next = { ...prev };
                    if (event.stage === 'SCAN_DONE') {
                        // Parse total from message
                        const match = event.message?.match(/(\d+) student sheets/);
                        if (match) next.total = parseInt(match[1]);
                    }
                    if (event.stage === 'SAVED') next.evaluated++;
                    if (event.stage === 'EVALUATING') next.inProgress++;
                    if (event.stage === 'FAILED') { next.failed++; next.inProgress = Math.max(0, next.inProgress - 1); }
                    if (event.stage === 'SAVED' && next.inProgress > 0) next.inProgress--;
                    if (event.flag) next.flagged++;
                    if (event.stage === 'COMPLETE' || event.stage === 'CANCELLED') {
                        next.inProgress = 0;
                    }
                    return next;
                });

                if (event.stage === 'COMPLETE' || event.stage === 'CANCELLED') {
                    setEvaluating(false);
                }
            });

            eventSourceRef.current = es;
        } catch (err) {
            alert('Failed to start: ' + err.message);
            setEvaluating(false);
        }
    }

    async function handleStop() {
        try {
            await stopEvaluation();
        } catch (err) {
            console.error('Stop failed:', err);
        }
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
        }
        setEvaluating(false);
    }

    useEffect(() => {
        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
            }
        };
    }, []);

    return (
        <div className="fade-in">
            <div className="page-header">
                <h2>Dashboard</h2>
                <p>Scan exam folders, start evaluation, and monitor progress</p>
            </div>

            {/* Action Buttons */}
            <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
                <button
                    id="btn-scan"
                    className="btn btn-outline btn-lg"
                    onClick={handleScan}
                    disabled={scanning || evaluating}
                >
                    {scanning ? (
                        <>
                            <span className="spinner" style={{ width: 16, height: 16 }} />
                            Scanning...
                        </>
                    ) : (
                        '🔍 Scan Folder'
                    )}
                </button>

                {scanResult && !evaluating && (
                    <button
                        id="btn-start-eval"
                        className="btn btn-success btn-lg"
                        onClick={handleStart}
                        disabled={!scanResult || scanResult.courses?.length === 0}
                    >
                        ▶ Start Evaluation
                    </button>
                )}

                {evaluating && (
                    <button
                        id="btn-stop-eval"
                        className="btn btn-danger btn-lg"
                        onClick={handleStop}
                    >
                        ⏹ Stop
                    </button>
                )}
            </div>

            {/* Stats Counters */}
            {(evaluating || events.length > 0) && (
                <div className="grid grid-4" style={{ marginBottom: 24 }}>
                    <div className="card stat-card">
                        <div className="stat-value">{stats.total}</div>
                        <div className="stat-label">Total</div>
                    </div>
                    <div className="card stat-card">
                        <div className="stat-value" style={{ background: 'var(--gradient-success)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                            {stats.evaluated}
                        </div>
                        <div className="stat-label">Evaluated</div>
                    </div>
                    <div className="card stat-card">
                        <div className="stat-value" style={{ background: 'var(--gradient-accent)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                            {stats.inProgress}
                        </div>
                        <div className="stat-label">In Progress</div>
                    </div>
                    <div className="card stat-card">
                        <div className="stat-value" style={{ background: 'var(--gradient-danger)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                            {stats.failed}
                        </div>
                        <div className="stat-label">Failed</div>
                    </div>
                </div>
            )}

            {/* Course Grid */}
            {scanResult && (
                <>
                    <h3 style={{ marginBottom: 16, fontSize: 18, fontWeight: 600 }}>
                        Courses ({scanResult.total_courses})
                    </h3>
                    {scanResult.incomplete_courses?.length > 0 && (
                        <div className="alert alert-warning" style={{ marginBottom: 16 }}>
                            ⚠️ Incomplete courses (missing QuestionPaper or AnswerKey):{' '}
                            {scanResult.incomplete_courses.join(', ')}
                        </div>
                    )}
                    <div className="grid grid-3" style={{ marginBottom: 24 }}>
                        {scanResult.courses?.map((course) => (
                            <CourseCard key={course.course_code} course={course} />
                        ))}
                    </div>
                </>
            )}

            {/* Progress Feed */}
            {events.length > 0 && (
                <div className="card" style={{ marginTop: 12 }}>
                    <div className="card-header">
                        <h3 className="card-title">📋 Progress Feed</h3>
                        <span className="badge badge-info">{events.length} events</span>
                    </div>
                    <ProgressFeed events={events} />
                </div>
            )}

            {/* Empty State */}
            {!scanResult && !scanning && (
                <div className="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                    </svg>
                    <h3>No scan results yet</h3>
                    <p>Click "Scan Folder" to discover exam papers and student sheets</p>
                </div>
            )}
        </div>
    );
}
