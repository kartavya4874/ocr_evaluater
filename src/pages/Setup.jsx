import React, { useState, useEffect } from 'react';
import { loadConfig, saveConfig, validateConfig } from '../lib/api';
import { openFolder } from '../lib/ipc';
import FolderInput from '../components/FolderInput';

export default function Setup() {
    const [config, setConfig] = useState({
        root_exam_folder: '',
        export_output_folder: '',
        openai_api_key: '',
        mongodb_uri: 'mongodb://localhost:27017',
        redis_url: 'redis://localhost:6379',
        distributed_mode: false,
        head_node_port: 8765,
        re_evaluate: false,
        max_concurrent_api_calls: 5,
        grading_scale: { 'O': 90, 'A+': 80, 'A': 70, 'B+': 60, 'B': 50, 'C': 40, 'F': 0 },
        selected_courses: 'ALL',
    });
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const [testing, setTesting] = useState(false);
    const [testResults, setTestResults] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadConfig()
            .then((data) => {
                if (data.config) setConfig(data.config);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    function updateConfig(key, value) {
        setConfig((prev) => ({ ...prev, [key]: value }));
        setSaved(false);
    }

    function updateGrade(grade, value) {
        setConfig((prev) => ({
            ...prev,
            grading_scale: { ...prev.grading_scale, [grade]: Number(value) },
        }));
        setSaved(false);
    }

    async function handleSave() {
        setSaving(true);
        try {
            await saveConfig(config);
            setSaved(true);
            setTimeout(() => setSaved(false), 3000);
        } catch (err) {
            alert('Failed to save: ' + err.message);
        }
        setSaving(false);
    }

    async function handleTest() {
        setTesting(true);
        setTestResults(null);
        try {
            // Save first
            await saveConfig(config);
            const result = await validateConfig();
            setTestResults(result.results);
        } catch (err) {
            setTestResults({ error: err.message });
        }
        setTesting(false);
    }

    if (loading) {
        return (
            <div className="empty-state">
                <div className="spinner spinner-lg"></div>
                <p style={{ marginTop: 16 }}>Loading configuration...</p>
            </div>
        );
    }

    return (
        <div className="fade-in">
            <div className="page-header">
                <h2>Setup & Configuration</h2>
                <p>Configure API keys, database connections, and exam folder paths</p>
            </div>

            {/* Folder Paths */}
            <div className="card" style={{ marginBottom: 20 }}>
                <div className="card-header">
                    <h3 className="card-title">📁 Folder Paths</h3>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    <FolderInput
                        label="Root Exam Folder"
                        value={config.root_exam_folder}
                        onChange={(val) => updateConfig('root_exam_folder', val)}
                    />
                    <FolderInput
                        label="Export Output Folder"
                        value={config.export_output_folder}
                        onChange={(val) => updateConfig('export_output_folder', val)}
                    />
                </div>
            </div>

            {/* API & Database */}
            <div className="grid grid-2" style={{ marginBottom: 20 }}>
                <div className="card">
                    <div className="card-header">
                        <h3 className="card-title">🔑 OpenAI API</h3>
                    </div>
                    <div className="input-group">
                        <label>API Key</label>
                        <input
                            id="input-api-key"
                            className="input"
                            type="password"
                            placeholder="sk-..."
                            value={config.openai_api_key}
                            onChange={(e) => updateConfig('openai_api_key', e.target.value)}
                        />
                    </div>
                </div>

                <div className="card">
                    <div className="card-header">
                        <h3 className="card-title">🗄️ MongoDB</h3>
                    </div>
                    <div className="input-group">
                        <label>Connection URI</label>
                        <input
                            id="input-mongodb-uri"
                            className="input"
                            type="text"
                            placeholder="mongodb://localhost:27017"
                            value={config.mongodb_uri}
                            onChange={(e) => updateConfig('mongodb_uri', e.target.value)}
                        />
                    </div>
                </div>
            </div>

            {/* Distributed Mode & Redis */}
            <div className="card" style={{ marginBottom: 20 }}>
                <div className="card-header">
                    <h3 className="card-title">⚡ Advanced</h3>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                    <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                            <div
                                className={`toggle ${config.distributed_mode ? 'active' : ''}`}
                                onClick={() => updateConfig('distributed_mode', !config.distributed_mode)}
                            >
                                <div className="toggle-knob" />
                            </div>
                            <span style={{ fontSize: 13.5 }}>Distributed Mode</span>
                        </div>

                        {config.distributed_mode && (
                            <div className="input-group" style={{ marginBottom: 12 }}>
                                <label>Redis URL</label>
                                <input
                                    id="input-redis-url"
                                    className="input"
                                    type="text"
                                    placeholder="redis://localhost:6379"
                                    value={config.redis_url}
                                    onChange={(e) => updateConfig('redis_url', e.target.value)}
                                />
                            </div>
                        )}

                        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                            <div
                                className={`toggle ${config.re_evaluate ? 'active' : ''}`}
                                onClick={() => updateConfig('re_evaluate', !config.re_evaluate)}
                            >
                                <div className="toggle-knob" />
                            </div>
                            <span style={{ fontSize: 13.5 }}>Re-evaluate existing results</span>
                        </div>
                    </div>

                    <div>
                        <div className="input-group" style={{ marginBottom: 12 }}>
                            <label>Max Concurrent API Calls</label>
                            <input
                                id="input-max-concurrent"
                                className="input"
                                type="number"
                                min="1"
                                max="20"
                                value={config.max_concurrent_api_calls}
                                onChange={(e) => updateConfig('max_concurrent_api_calls', parseInt(e.target.value) || 5)}
                            />
                        </div>

                        <div className="input-group">
                            <label>Selected Courses (comma-separated or ALL)</label>
                            <input
                                id="input-selected-courses"
                                className="input"
                                type="text"
                                placeholder="ALL"
                                value={config.selected_courses}
                                onChange={(e) => updateConfig('selected_courses', e.target.value)}
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* Grading Scale */}
            <div className="card" style={{ marginBottom: 20 }}>
                <div className="card-header">
                    <h3 className="card-title">📊 Grading Scale</h3>
                </div>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                    {Object.entries(config.grading_scale).map(([grade, minPct]) => (
                        <div key={grade} className="input-group" style={{ width: 90 }}>
                            <label>{grade}</label>
                            <input
                                className="input"
                                type="number"
                                min="0"
                                max="100"
                                value={minPct}
                                onChange={(e) => updateGrade(grade, e.target.value)}
                            />
                        </div>
                    ))}
                </div>
            </div>

            {/* Connection Test */}
            {testResults && (
                <div className="card" style={{ marginBottom: 20 }}>
                    <div className="card-header">
                        <h3 className="card-title">Connection Test Results</h3>
                    </div>
                    {testResults.error ? (
                        <div className="alert alert-error">{testResults.error}</div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                            <div className="connection-test">
                                <span className="service-name">MongoDB</span>
                                <span className="status-badge">
                                    <span className={`status-dot ${testResults.mongodb ? 'online' : 'offline'}`} />
                                    {testResults.mongodb ? 'Connected' : testResults.mongodb_error || 'Failed'}
                                </span>
                            </div>
                            <div className="connection-test">
                                <span className="service-name">OpenAI</span>
                                <span className="status-badge">
                                    <span className={`status-dot ${testResults.openai ? 'online' : 'offline'}`} />
                                    {testResults.openai ? 'Connected' : testResults.openai_error || 'Failed'}
                                </span>
                            </div>
                            {testResults.redis !== null && (
                                <div className="connection-test">
                                    <span className="service-name">Redis</span>
                                    <span className="status-badge">
                                        <span className={`status-dot ${testResults.redis ? 'online' : 'offline'}`} />
                                        {testResults.redis ? 'Connected' : testResults.redis_error || 'Failed'}
                                    </span>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <button id="btn-save-config" className="btn btn-primary btn-lg" onClick={handleSave} disabled={saving}>
                    {saving ? 'Saving...' : saved ? '✓ Saved' : 'Save Configuration'}
                </button>
                <button id="btn-test-connections" className="btn btn-outline btn-lg" onClick={handleTest} disabled={testing}>
                    {testing ? (
                        <>
                            <span className="spinner" style={{ width: 16, height: 16 }} />
                            Testing...
                        </>
                    ) : (
                        'Test Connections'
                    )}
                </button>
            </div>
        </div>
    );
}
