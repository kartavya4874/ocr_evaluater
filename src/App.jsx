import React, { useState, useEffect } from 'react';
import { initBackendPort } from './lib/api';
import { getAppVersion } from './lib/ipc';

import Setup from './pages/Setup';
import Dashboard from './pages/Dashboard';
import Results from './pages/Results';
import Export from './pages/Export';
import Workers from './pages/Workers';

const NAV_ITEMS = [
    { id: 'setup', label: 'Setup', icon: 'settings' },
    { id: 'dashboard', label: 'Dashboard', icon: 'activity' },
    { id: 'results', label: 'Results', icon: 'clipboard' },
    { id: 'export', label: 'Export', icon: 'download' },
    { id: 'workers', label: 'Workers', icon: 'cpu' },
];

const ICONS = {
    settings: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
    ),
    activity: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
    ),
    clipboard: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /><rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
        </svg>
    ),
    download: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
        </svg>
    ),
    cpu: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="4" y="4" width="16" height="16" rx="2" ry="2" /><rect x="9" y="9" width="6" height="6" /><line x1="9" y1="1" x2="9" y2="4" /><line x1="15" y1="1" x2="15" y2="4" /><line x1="9" y1="20" x2="9" y2="23" /><line x1="15" y1="20" x2="15" y2="23" /><line x1="20" y1="9" x2="23" y2="9" /><line x1="20" y1="14" x2="23" y2="14" /><line x1="1" y1="9" x2="4" y2="9" /><line x1="1" y1="14" x2="4" y2="14" />
        </svg>
    ),
};

export default function App() {
    const [page, setPage] = useState('setup');
    const [version, setVersion] = useState('');
    const [backendStatus, setBackendStatus] = useState('connecting');

    useEffect(() => {
        async function init() {
            await initBackendPort();
            try {
                const v = await getAppVersion();
                setVersion(v);
            } catch {
                setVersion('1.0.0');
            }

            // Check backend health
            try {
                const { checkHealth } = await import('./lib/api');
                await checkHealth();
                setBackendStatus('online');
            } catch {
                setBackendStatus('offline');
            }
        }
        init();
    }, []);

    function renderPage() {
        switch (page) {
            case 'setup': return <Setup />;
            case 'dashboard': return <Dashboard />;
            case 'results': return <Results />;
            case 'export': return <Export />;
            case 'workers': return <Workers />;
            default: return <Setup />;
        }
    }

    return (
        <div className="app-layout">
            {/* Sidebar */}
            <aside className="sidebar">
                <div className="sidebar-logo">
                    <h1>Exam Evaluator</h1>
                    <div className="version">v{version || '1.0.0'}</div>
                </div>

                <nav className="sidebar-nav">
                    {NAV_ITEMS.map((item) => (
                        <div
                            key={item.id}
                            id={`nav-${item.id}`}
                            className={`nav-item ${page === item.id ? 'active' : ''}`}
                            onClick={() => setPage(item.id)}
                        >
                            {ICONS[item.icon]}
                            <span>{item.label}</span>
                        </div>
                    ))}
                </nav>

                <div className="sidebar-footer">
                    <span
                        className={`status-dot ${backendStatus === 'online' ? 'online' : 'offline'}`}
                    />
                    <span style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>
                        Backend {backendStatus}
                    </span>
                </div>
            </aside>

            {/* Main Content */}
            <main className="main-content">
                {renderPage()}
            </main>
        </div>
    );
}
