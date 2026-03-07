import React from 'react';
import { openFolder } from '../lib/ipc';

export default function FolderInput({ label, value, onChange }) {
    async function handleBrowse() {
        const folder = await openFolder();
        if (folder) {
            onChange(folder);
        }
    }

    return (
        <div className="input-group">
            <label>{label}</label>
            <div className="input-with-btn">
                <input
                    className="input"
                    type="text"
                    placeholder="Select a folder..."
                    value={value || ''}
                    onChange={(e) => onChange(e.target.value)}
                    readOnly
                />
                <button className="btn btn-outline" onClick={handleBrowse}>
                    Browse
                </button>
            </div>
        </div>
    );
}
