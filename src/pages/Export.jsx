import React, { useState, useEffect } from 'react';
import { getResults, exportCourse, exportAll } from '../lib/api';
import { saveFile } from '../lib/ipc';

export default function Export() {
    const [courses, setCourses] = useState([]);
    const [selected, setSelected] = useState({});
    const [exporting, setExporting] = useState(false);
    const [recentExports, setRecentExports] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        getResults()
            .then((data) => {
                setCourses(data.courses || []);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    function toggleCourse(code) {
        setSelected((prev) => ({ ...prev, [code]: !prev[code] }));
    }

    function selectAll() {
        const all = {};
        courses.forEach((c) => { all[c.course_code] = true; });
        setSelected(all);
    }

    function selectNone() {
        setSelected({});
    }

    async function handleExportSelected() {
        const selectedCourses = Object.keys(selected).filter((k) => selected[k]);
        if (selectedCourses.length === 0) return;

        setExporting(true);
        try {
            for (const code of selectedCourses) {
                const blob = await exportCourse(code);
                const filename = `${code}_Results.xlsx`;

                // Try native save dialog
                const savePath = await saveFile({
                    title: `Save ${code} Results`,
                    defaultPath: filename,
                    filters: [{ name: 'Excel Files', extensions: ['xlsx'] }],
                });

                if (savePath) {
                    // In Electron, we'd write the blob to the path, but for download:
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    a.click();
                    URL.revokeObjectURL(url);

                    setRecentExports((prev) => [
                        { name: filename, date: new Date().toLocaleString(), path: savePath },
                        ...prev,
                    ]);
                }
            }
        } catch (err) {
            alert('Export failed: ' + err.message);
        }
        setExporting(false);
    }

    async function handleExportAll() {
        setExporting(true);
        try {
            const blob = await exportAll();
            const filename = `All_Results.zip`;

            const savePath = await saveFile({
                title: 'Save All Results',
                defaultPath: filename,
                filters: [{ name: 'ZIP Files', extensions: ['zip'] }],
            });

            if (savePath) {
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                a.click();
                URL.revokeObjectURL(url);

                setRecentExports((prev) => [
                    { name: filename, date: new Date().toLocaleString(), path: savePath },
                    ...prev,
                ]);
            }
        } catch (err) {
            alert('Export failed: ' + err.message);
        }
        setExporting(false);
    }

    if (loading) {
        return (
            <div className="empty-state">
                <div className="spinner spinner-lg"></div>
                <p style={{ marginTop: 16 }}>Loading courses...</p>
            </div>
        );
    }

    return (
        <div className="fade-in">
            <div className="page-header">
                <h2>Export</h2>
                <p>Export evaluation results to Excel spreadsheets</p>
            </div>

            {courses.length === 0 ? (
                <div className="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
                    </svg>
                    <h3>No results to export</h3>
                    <p>Run an evaluation first to generate results</p>
                </div>
            ) : (
                <>
                    {/* Course Checklist */}
                    <div className="card" style={{ marginBottom: 20 }}>
                        <div className="card-header">
                            <h3 className="card-title">Select Courses</h3>
                            <div style={{ display: 'flex', gap: 8 }}>
                                <button className="btn btn-outline btn-sm" onClick={selectAll}>Select All</button>
                                <button className="btn btn-outline btn-sm" onClick={selectNone}>Clear</button>
                            </div>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
                            {courses.map((course) => (
                                <label key={course.course_code} className="checkbox" style={{ padding: '8px 12px', borderRadius: 8, background: selected[course.course_code] ? 'rgba(129,140,248,0.08)' : 'transparent' }}>
                                    <input
                                        type="checkbox"
                                        checked={!!selected[course.course_code]}
                                        onChange={() => toggleCourse(course.course_code)}
                                    />
                                    <div>
                                        <div style={{ fontWeight: 600 }}>{course.course_code}</div>
                                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                            {course.student_count} students
                                        </div>
                                    </div>
                                </label>
                            ))}
                        </div>
                    </div>

                    {/* Export Actions */}
                    <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
                        <button
                            id="btn-export-selected"
                            className="btn btn-primary btn-lg"
                            onClick={handleExportSelected}
                            disabled={exporting || Object.values(selected).filter(Boolean).length === 0}
                        >
                            {exporting ? 'Exporting...' : `Export Selected (${Object.values(selected).filter(Boolean).length})`}
                        </button>
                        <button
                            id="btn-export-all"
                            className="btn btn-outline btn-lg"
                            onClick={handleExportAll}
                            disabled={exporting}
                        >
                            Export All as ZIP
                        </button>
                    </div>

                    {/* Recent Exports */}
                    {recentExports.length > 0 && (
                        <div className="card">
                            <div className="card-header">
                                <h3 className="card-title">Recent Exports</h3>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                {recentExports.map((exp, i) => (
                                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px', background: 'var(--bg-glass)', borderRadius: 8 }}>
                                        <span style={{ fontSize: 18 }}>📄</span>
                                        <div style={{ flex: 1 }}>
                                            <div style={{ fontWeight: 600, fontSize: 13 }}>{exp.name}</div>
                                            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{exp.date}</div>
                                        </div>
                                        <span className="badge badge-success">✓ Saved</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
