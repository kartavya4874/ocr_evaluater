/**
 * API helper — all fetch calls to the Python backend.
 */

let backendPort = 8765;

export async function initBackendPort() {
    if (window.electronAPI) {
        try {
            backendPort = await window.electronAPI.getBackendPort();
        } catch {
            backendPort = 8765;
        }
    }
}

function getBaseUrl() {
    return `http://127.0.0.1:${backendPort}`;
}

async function request(method, path, body = null) {
    const url = `${getBaseUrl()}${path}`;
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) {
        options.body = JSON.stringify(body);
    }
    const res = await fetch(url, options);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
}

// --- Health ---
export const checkHealth = () => request('GET', '/health');

// --- Config ---
export const loadConfig = () => request('GET', '/config/load');
export const saveConfig = (config) => request('POST', '/config/save', { config });
export const validateConfig = () => request('POST', '/config/validate');

// --- Scan ---
export const scanFolder = () => request('GET', '/scan');

// --- Evaluate ---
export const startEvaluation = () => request('POST', '/evaluate/start');
export const stopEvaluation = () => request('POST', '/evaluate/stop');

export function subscribeProgress(onEvent) {
    const url = `${getBaseUrl()}/evaluate/progress`;
    const eventSource = new EventSource(url);

    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.stage !== 'KEEPALIVE') {
                onEvent(data);
            }
        } catch {
            // Ignore parse errors
        }
    };

    eventSource.onerror = () => {
        // Reconnection is automatic with EventSource
    };

    return eventSource;
}

// --- Results ---
export const getResults = () => request('GET', '/results');
export const getResultsByCourse = (courseCode) => request('GET', `/results/${courseCode}`);
export const getResultDetail = (courseCode, roll) => request('GET', `/results/${courseCode}/${roll}`);

// --- Export ---
export async function exportCourse(courseCode) {
    const url = `${getBaseUrl()}/export/${courseCode}`;
    const res = await fetch(url, { method: 'POST' });
    if (!res.ok) throw new Error('Export failed');
    return res.blob();
}

export async function exportAll() {
    const url = `${getBaseUrl()}/export/all`;
    const res = await fetch(url, { method: 'POST' });
    if (!res.ok) throw new Error('Export failed');
    return res.blob();
}

// --- Workers ---
export const getWorkers = () => request('GET', '/workers');
export const registerWorker = (data) => request('POST', '/workers/register', data);
export const workerHeartbeat = (data) => request('POST', '/workers/heartbeat', data);
