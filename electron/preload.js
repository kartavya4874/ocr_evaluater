/**
 * Preload script — context bridge for safe IPC communication.
 * Exposes selected Electron APIs to the React renderer process.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // Dialog operations
    openFolder: () => ipcRenderer.invoke('dialog:openFolder'),
    saveFile: (options) => ipcRenderer.invoke('dialog:saveFile', options),

    // App info
    getBackendPort: () => ipcRenderer.invoke('app:getBackendPort'),
    getVersion: () => ipcRenderer.invoke('app:getVersion'),

    // Window controls
    minimizeWindow: () => ipcRenderer.invoke('window:minimize'),
    maximizeWindow: () => ipcRenderer.invoke('window:maximize'),
    closeWindow: () => ipcRenderer.invoke('window:close'),
});
