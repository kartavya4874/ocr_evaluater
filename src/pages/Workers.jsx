import React, { useState, useEffect } from 'react';
import { getWorkers, loadConfig } from '../lib/api';
import WorkerCard from '../components/WorkerCard';

export default function Workers() {
    const [workers, setWorkers] = useState([]);
    const [config, setConfig] = useState({});
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function fetch() {
            try {
                const [workerData, configData] = await Promise.all([
                    getWorkers().catch(() => ({ workers: [] })),
                    loadConfig().catch(() => ({ config: {} })),
                ]);
                setWorkers(workerData.workers || []);
                setConfig(configData.config || {});
            } catch {
                // Ignore
            }
            setLoading(false);
        }
        fetch();
        const interval = setInterval(fetch, 10000);
        return () => clearInterval(interval);
    }, []);

    const startCommand = `python worker.py --head http://<HEAD_IP>:${config.head_node_port || 8765} --id worker_2 --threads 4`;

    if (!config.distributed_mode) {
        return (
            <div className="fade-in">
                <div className="page-header">
                    <h2>Workers</h2>
                    <p>Distributed processing workers</p>
                </div>
                <div className="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <rect x="4" y="4" width="16" height="16" rx="2" ry="2" />
                        <rect x="9" y="9" width="6" height="6" />
                    </svg>
                    <h3>Distributed mode is disabled</h3>
                    <p>Enable distributed mode in Setup to use worker nodes</p>
                </div>
            </div>
        );
    }

    return (
        <div className="fade-in">
            <div className="page-header">
                <h2>Workers</h2>
                <p>Manage distributed processing workers</p>
            </div>

            {/* Start Command */}
            <div className="card" style={{ marginBottom: 20 }}>
                <div className="card-header">
                    <h3 className="card-title">🚀 Start a Worker</h3>
                </div>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12 }}>
                    Run this command on another machine to start a worker node:
                </p>
                <div className="copy-block">
                    <code>{startCommand}</code>
                    <button
                        className="btn btn-outline btn-sm"
                        onClick={() => {
                            navigator.clipboard.writeText(startCommand);
                        }}
                    >
                        📋 Copy
                    </button>
                </div>
            </div>

            {/* Worker Cards */}
            {loading ? (
                <div className="empty-state">
                    <div className="spinner spinner-lg"></div>
                </div>
            ) : workers.length === 0 ? (
                <div className="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <rect x="4" y="4" width="16" height="16" rx="2" ry="2" />
                        <rect x="9" y="9" width="6" height="6" />
                    </svg>
                    <h3>No workers connected</h3>
                    <p>Start a worker using the command above</p>
                </div>
            ) : (
                <div className="grid grid-3">
                    {workers.map((worker) => (
                        <WorkerCard key={worker.worker_id} worker={worker} />
                    ))}
                </div>
            )}
        </div>
    );
}
