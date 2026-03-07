/**
 * Backend Manager — spawns/kills the Python FastAPI process, finds free port.
 */

const { spawn } = require('child_process');
const path = require('path');
const net = require('net');
const http = require('http');

let pythonProcess = null;
let backendPort = 8765;

/**
 * Find a free port starting from the given port.
 */
async function findFreePort(startPort = 8765) {
    return new Promise((resolve, reject) => {
        const server = net.createServer();
        server.listen(startPort, '127.0.0.1', () => {
            const port = server.address().port;
            server.close(() => resolve(port));
        });
        server.on('error', () => {
            // Port in use, try next
            resolve(findFreePort(startPort + 1));
        });
    });
}

/**
 * Get the path to the Python executable and backend module.
 */
function getBackendPaths() {
    const isDev = !require('electron').app.isPackaged;

    if (isDev) {
        // Development mode — backend is in project root
        const projectRoot = path.join(__dirname, '..');
        return {
            cwd: projectRoot,
            pythonCmd: 'python',
            args: ['-m', 'uvicorn', 'backend.main:app', '--port', String(backendPort), '--host', '127.0.0.1'],
        };
    } else {
        // Production mode — backend is in resources
        const resourcesPath = process.resourcesPath;
        const backendPath = path.join(resourcesPath, 'backend');
        return {
            cwd: path.join(resourcesPath),
            pythonCmd: 'python',
            args: ['-m', 'uvicorn', 'backend.main:app', '--port', String(backendPort), '--host', '127.0.0.1'],
        };
    }
}

/**
 * Spawn the Python backend process.
 */
async function startBackend() {
    backendPort = await findFreePort(8765);
    console.log(`[Backend Manager] Starting backend on port ${backendPort}`);

    const { cwd, pythonCmd, args } = getBackendPaths();

    // Set environment variables
    const env = {
        ...process.env,
        EXAM_EVAL_CONFIG_DIR: require('electron').app.getPath('userData'),
        PYTHONUNBUFFERED: '1',
    };

    pythonProcess = spawn(pythonCmd, args, {
        cwd,
        env,
        stdio: ['pipe', 'pipe', 'pipe'],
    });

    pythonProcess.stdout.on('data', (data) => {
        console.log(`[Python] ${data.toString().trim()}`);
    });

    pythonProcess.stderr.on('data', (data) => {
        console.error(`[Python ERR] ${data.toString().trim()}`);
    });

    pythonProcess.on('error', (err) => {
        console.error(`[Backend Manager] Failed to start Python: ${err.message}`);
    });

    pythonProcess.on('exit', (code, signal) => {
        console.log(`[Backend Manager] Python exited with code ${code}, signal ${signal}`);
        pythonProcess = null;
    });

    // Poll health endpoint until ready
    const ready = await pollHealth(backendPort, 30000, 500);
    if (!ready) {
        throw new Error('Backend failed to start within timeout');
    }

    console.log(`[Backend Manager] Backend is ready on port ${backendPort}`);
    return backendPort;
}

/**
 * Poll the health endpoint until it responds or timeout.
 */
function pollHealth(port, timeoutMs = 30000, intervalMs = 500) {
    return new Promise((resolve) => {
        const start = Date.now();

        const check = () => {
            if (Date.now() - start > timeoutMs) {
                resolve(false);
                return;
            }

            const req = http.get(`http://127.0.0.1:${port}/health`, (res) => {
                if (res.statusCode === 200) {
                    resolve(true);
                } else {
                    setTimeout(check, intervalMs);
                }
            });

            req.on('error', () => {
                setTimeout(check, intervalMs);
            });

            req.setTimeout(1000, () => {
                req.destroy();
                setTimeout(check, intervalMs);
            });
        };

        check();
    });
}

/**
 * Kill the Python backend process.
 */
function stopBackend() {
    if (pythonProcess) {
        console.log('[Backend Manager] Stopping backend...');
        pythonProcess.kill('SIGTERM');

        // Force kill after 5 seconds
        setTimeout(() => {
            if (pythonProcess) {
                pythonProcess.kill('SIGKILL');
                pythonProcess = null;
            }
        }, 5000);
    }
}

/**
 * Get the current backend port.
 */
function getBackendPort() {
    return backendPort;
}

/**
 * Check if backend is running.
 */
function isBackendRunning() {
    return pythonProcess !== null;
}

module.exports = {
    startBackend,
    stopBackend,
    getBackendPort,
    isBackendRunning,
    findFreePort,
};
