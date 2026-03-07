/**
 * Electron Main Process — window creation, IPC handlers, app lifecycle.
 */

const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { startBackend, stopBackend, getBackendPort } = require('./backend_manager');

let mainWindow = null;
let backendReady = false;

// Prevent multiple instances
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
    app.quit();
}

async function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1024,
        minHeight: 700,
        title: 'Exam Evaluator',
        icon: path.join(__dirname, '..', 'public', 'icon.png'),
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true,
            sandbox: false,
        },
        show: false,
        backgroundColor: '#0a0a1a',
        titleBarStyle: 'default',
        autoHideMenuBar: true,
    });

    // Show loading screen while backend starts
    mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(getLoadingHTML())}`);
    mainWindow.show();

    try {
        // Start the Python backend
        const port = await startBackend();
        backendReady = true;
        console.log(`[Electron] Backend ready on port ${port}`);

        // Load the React app
        const isDev = !app.isPackaged;
        if (isDev) {
            mainWindow.loadURL('http://localhost:5173');
            // Optionally open DevTools in dev mode
            // mainWindow.webContents.openDevTools();
        } else {
            mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
        }
    } catch (error) {
        console.error('[Electron] Backend startup failed:', error);
        dialog.showErrorBox(
            'Backend Failed to Start',
            'The Python backend failed to start. Please check that Python 3.11+ is installed and all dependencies are available.\n\nError: ' + error.message
        );
        app.quit();
    }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

// --- IPC Handlers ---

ipcMain.handle('dialog:openFolder', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openDirectory'],
        title: 'Select Folder',
    });
    if (result.canceled) return null;
    return result.filePaths[0];
});

ipcMain.handle('dialog:saveFile', async (event, options = {}) => {
    const result = await dialog.showSaveDialog(mainWindow, {
        title: options.title || 'Save File',
        defaultPath: options.defaultPath || 'export.xlsx',
        filters: options.filters || [
            { name: 'Excel Files', extensions: ['xlsx'] },
            { name: 'All Files', extensions: ['*'] },
        ],
    });
    if (result.canceled) return null;
    return result.filePath;
});

ipcMain.handle('app:getBackendPort', () => {
    return getBackendPort();
});

ipcMain.handle('app:getVersion', () => {
    return app.getVersion();
});

ipcMain.handle('window:minimize', () => {
    mainWindow?.minimize();
});

ipcMain.handle('window:maximize', () => {
    if (mainWindow?.isMaximized()) {
        mainWindow.unmaximize();
    } else {
        mainWindow?.maximize();
    }
});

ipcMain.handle('window:close', () => {
    mainWindow?.close();
});

// --- App Lifecycle ---

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    stopBackend();
    app.quit();
});

app.on('before-quit', () => {
    stopBackend();
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});

app.on('second-instance', () => {
    if (mainWindow) {
        if (mainWindow.isMinimized()) mainWindow.restore();
        mainWindow.focus();
    }
});

// --- Loading Screen HTML ---

function getLoadingHTML() {
    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: #0a0a1a;
      color: #e2e8f0;
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
      overflow: hidden;
    }
    .container {
      text-align: center;
    }
    .logo {
      font-size: 48px;
      font-weight: 800;
      background: linear-gradient(135deg, #818cf8, #c084fc, #f472b6);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 24px;
    }
    .subtitle {
      font-size: 16px;
      color: #94a3b8;
      margin-bottom: 40px;
    }
    .spinner {
      width: 48px;
      height: 48px;
      border: 3px solid rgba(129, 140, 248, 0.2);
      border-top-color: #818cf8;
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin: 0 auto 20px;
    }
    .status {
      font-size: 14px;
      color: #64748b;
      animation: pulse 2s ease-in-out infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    @keyframes pulse {
      0%, 100% { opacity: 0.5; }
      50% { opacity: 1; }
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="logo">Exam Evaluator</div>
    <div class="subtitle">Automated Evaluation System</div>
    <div class="spinner"></div>
    <div class="status">Starting backend services...</div>
  </div>
</body>
</html>`;
}
