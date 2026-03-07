/**
 * IPC helpers — wraps Electron context bridge calls with safe fallbacks.
 */

export async function openFolder() {
    if (window.electronAPI) {
        return window.electronAPI.openFolder();
    }
    // Browser fallback: prompt for path
    return prompt('Enter folder path:');
}

export async function saveFile(options = {}) {
    if (window.electronAPI) {
        return window.electronAPI.saveFile(options);
    }
    return prompt('Enter save path:', options.defaultPath || 'export.xlsx');
}

export async function getBackendPort() {
    if (window.electronAPI) {
        return window.electronAPI.getBackendPort();
    }
    return 8765;
}

export async function getAppVersion() {
    if (window.electronAPI) {
        return window.electronAPI.getVersion();
    }
    return '1.0.0-dev';
}

export function isElectron() {
    return !!window.electronAPI;
}
