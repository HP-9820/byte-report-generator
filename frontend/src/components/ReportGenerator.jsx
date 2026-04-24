// ─────────────────────────────────────────────────────────────
// ReportGenerator.jsx
// Drop this into your frontend/src/components/ folder
// ─────────────────────────────────────────────────────────────
//
// Replace your existing upload + generate UI with this component.
// It handles: file upload → generation → live progress → download
//
// Props:
//   authToken  <string>   JWT token from your auth context
//
// Example:
//   import ReportGenerator from './components/ReportGenerator';
//   <ReportGenerator authToken={user.token} />
//
// ─────────────────────────────────────────────────────────────

import { useState, useRef } from 'react';
import { useReportGeneration } from '../hooks/useReportGeneration';

export default function ReportGenerator({ authToken }) {
    const [file, setFile] = useState(null);
    const [count, setCount] = useState('');
    const [dragOver, setDragOver] = useState(false);
    const fileInputRef = useRef(null);

    const {
        startGeneration,
        status,
        progress,
        total,
        currentName,
        downloadUrl,
        fileName,
        error,
        reset,
    } = useReportGeneration();

    // ── percentage for progress bar ──
    const pct = total > 0 ? Math.round((progress / total) * 100) : 0;

    // ── File selection ──
    const handleFile = (f) => {
        if (!f) return;
        if (!f.name.match(/\.(xlsx|xls|csv)$/i)) {
            alert('Please upload an Excel (.xlsx / .xls) or CSV file.');
            return;
        }
        setFile(f);
        reset();
    };

    const onDrop = (e) => {
        e.preventDefault();
        setDragOver(false);
        handleFile(e.dataTransfer.files[0]);
    };

    // ── Start ──
    const handleGenerate = async () => {
        if (!file) return;
        const parsedCount = parseInt(count, 10) || null;
        await startGeneration(file, parsedCount, authToken);
    };

    // ── Download helper ──
    const handleDownload = () => {
        if (!downloadUrl) return;
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = fileName || 'Reports.docx';
        a.click();
    };

    return (
        <div style={styles.wrapper}>

            {/* ── UPLOAD CARD ── */}
            {status === 'idle' && (
                <div style={styles.card}>
                    <h2 style={styles.title}>Generate Reports</h2>

                    {/* Drop zone */}
                    <div
                        style={{ ...styles.dropzone, ...(dragOver ? styles.dropzoneActive : {}) }}
                        onClick={() => fileInputRef.current?.click()}
                        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                        onDragLeave={() => setDragOver(false)}
                        onDrop={onDrop}
                    >
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".xlsx,.xls,.csv"
                            style={{ display: 'none' }}
                            onChange={(e) => handleFile(e.target.files[0])}
                        />
                        {file ? (
                            <>
                                <span style={styles.fileIcon}>📄</span>
                                <p style={styles.fileName}>{file.name}</p>
                                <p style={styles.changeHint}>Click to change file</p>
                            </>
                        ) : (
                            <>
                                <span style={styles.uploadIcon}>⬆️</span>
                                <p style={styles.dropText}>Drag & drop or click to upload</p>
                                <p style={styles.dropHint}>.xlsx · .xls · .csv</p>
                            </>
                        )}
                    </div>

                    {/* Count input */}
                    <label style={styles.label}>
                        Reports to generate
                        <input
                            type="number"
                            min="1"
                            placeholder="Leave blank for all students"
                            value={count}
                            onChange={(e) => setCount(e.target.value)}
                            style={styles.input}
                        />
                    </label>

                    {/* Generate button */}
                    <button
                        style={{ ...styles.btn, ...(file ? {} : styles.btnDisabled) }}
                        disabled={!file}
                        onClick={handleGenerate}
                    >
                        Generate My Reports →
                    </button>
                </div>
            )}

            {/* ── PROGRESS CARD ── */}
            {status === 'running' && (
                <div style={styles.card}>
                    <h2 style={styles.title}>Generating Reports…</h2>
                    <p style={styles.subtitle}>
                        Please keep this tab open. This may take a few minutes for large classes.
                    </p>

                    {/* Progress bar */}
                    <div style={styles.barTrack}>
                        <div style={{ ...styles.barFill, width: `${pct}%` }} />
                    </div>

                    <div style={styles.progressRow}>
                        <span style={styles.progressCount}>{progress} / {total} students</span>
                        <span style={styles.progressPct}>{pct}%</span>
                    </div>

                    {currentName && (
                        <p style={styles.currentName}>
                            ✏️ Processing: <strong>{currentName}</strong>
                        </p>
                    )}

                    {/* Animated dots */}
                    <p style={styles.waitNote}>
                        <LoadingDots /> Analysing with AI
                    </p>
                </div>
            )}

            {/* ── DONE CARD ── */}
            {status === 'done' && (
                <div style={styles.card}>
                    <div style={styles.successIcon}>✅</div>
                    <h2 style={styles.title}>All {total} Reports Ready!</h2>
                    <p style={styles.subtitle}>Your consolidated report document has been generated.</p>

                    <button style={styles.btn} onClick={handleDownload}>
                        ⬇ Download {fileName || 'Reports.docx'}
                    </button>

                    <button style={styles.btnSecondary} onClick={() => { reset(); setFile(null); setCount(''); }}>
                        Generate Another Class
                    </button>
                </div>
            )}

            {/* ── ERROR CARD ── */}
            {status === 'error' && (
                <div style={styles.card}>
                    <div style={styles.errorIcon}>❌</div>
                    <h2 style={styles.title}>Something Went Wrong</h2>
                    <p style={styles.errorMsg}>{error}</p>
                    <p style={styles.subtitle}>
                        Any reports that were completed may already be in <strong>My Reports</strong>.
                    </p>
                    <button style={styles.btn} onClick={() => { reset(); }}>
                        Try Again
                    </button>
                </div>
            )}
        </div>
    );
}

// ── Tiny animated dots component ──
function LoadingDots() {
    return (
        <span style={styles.dots}>
            <span style={{ ...styles.dot, animationDelay: '0s' }}>.</span>
            <span style={{ ...styles.dot, animationDelay: '0.3s' }}>.</span>
            <span style={{ ...styles.dot, animationDelay: '0.6s' }}>.</span>
        </span>
    );
}

// ─────────────────────────────────────────────
// INLINE STYLES  (keeps component self-contained)
// Replace with your Tailwind classes if preferred
// ─────────────────────────────────────────────
const styles = {
    wrapper: {
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '60vh',
        padding: '24px',
    },
    card: {
        background: 'rgba(255,255,255,0.08)',
        backdropFilter: 'blur(16px)',
        border: '1px dashed rgba(255,255,255,0.25)',
        borderRadius: '16px',
        padding: '40px 48px',
        width: '100%',
        maxWidth: '560px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        color: '#fff',
    },
    title: {
        margin: 0,
        fontSize: '22px',
        fontWeight: 700,
        textAlign: 'center',
    },
    subtitle: {
        margin: 0,
        fontSize: '13px',
        opacity: 0.7,
        textAlign: 'center',
        lineHeight: 1.5,
    },
    dropzone: {
        border: '2px dashed rgba(255,255,255,0.3)',
        borderRadius: '12px',
        padding: '32px 16px',
        textAlign: 'center',
        cursor: 'pointer',
        transition: 'border-color 0.2s, background 0.2s',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '8px',
    },
    dropzoneActive: {
        borderColor: '#4ade80',
        background: 'rgba(74,222,128,0.08)',
    },
    uploadIcon: { fontSize: '32px' },
    fileIcon: { fontSize: '32px' },
    dropText: { margin: 0, fontSize: '15px', fontWeight: 600 },
    dropHint: { margin: 0, fontSize: '12px', opacity: 0.55 },
    fileName: { margin: 0, fontSize: '15px', fontWeight: 600, wordBreak: 'break-all' },
    changeHint: { margin: 0, fontSize: '12px', opacity: 0.55 },
    label: {
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
        fontSize: '13px',
        fontWeight: 600,
        letterSpacing: '0.05em',
        textTransform: 'uppercase',
        opacity: 0.8,
    },
    input: {
        background: 'rgba(255,255,255,0.12)',
        border: '1px solid rgba(255,255,255,0.25)',
        borderRadius: '8px',
        padding: '10px 14px',
        color: '#fff',
        fontSize: '15px',
        outline: 'none',
        width: '140px',
        alignSelf: 'flex-start',
    },
    btn: {
        background: '#4ade80',
        color: '#000',
        border: 'none',
        borderRadius: '10px',
        padding: '14px 24px',
        fontSize: '15px',
        fontWeight: 700,
        cursor: 'pointer',
        transition: 'opacity 0.15s',
        textAlign: 'center',
    },
    btnDisabled: {
        opacity: 0.4,
        cursor: 'not-allowed',
    },
    btnSecondary: {
        background: 'transparent',
        color: '#fff',
        border: '1px solid rgba(255,255,255,0.35)',
        borderRadius: '10px',
        padding: '12px 24px',
        fontSize: '14px',
        fontWeight: 600,
        cursor: 'pointer',
        textAlign: 'center',
    },
    barTrack: {
        background: 'rgba(255,255,255,0.12)',
        borderRadius: '999px',
        height: '10px',
        overflow: 'hidden',
    },
    barFill: {
        height: '100%',
        background: 'linear-gradient(90deg, #4ade80, #22d3ee)',
        borderRadius: '999px',
        transition: 'width 0.5s ease',
    },
    progressRow: {
        display: 'flex',
        justifyContent: 'space-between',
        fontSize: '13px',
        opacity: 0.75,
    },
    progressCount: { fontWeight: 600 },
    progressPct: { fontWeight: 700 },
    currentName: {
        fontSize: '13px',
        opacity: 0.8,
        margin: 0,
        textAlign: 'center',
    },
    waitNote: {
        fontSize: '13px',
        opacity: 0.6,
        textAlign: 'center',
        margin: 0,
    },
    dots: { display: 'inline-flex', gap: '1px' },
    dot: {
        display: 'inline-block',
        animation: 'blink 1.2s infinite',
        fontSize: '18px',
        lineHeight: 1,
    },
    successIcon: { fontSize: '48px', textAlign: 'center' },
    errorIcon: { fontSize: '48px', textAlign: 'center' },
    errorMsg: {
        background: 'rgba(239,68,68,0.15)',
        border: '1px solid rgba(239,68,68,0.4)',
        borderRadius: '8px',
        padding: '12px 16px',
        fontSize: '13px',
        color: '#fca5a5',
        margin: 0,
        lineHeight: 1.5,
    },
};

/*
  Add this CSS once in your global stylesheet or index.css:

  @keyframes blink {
    0%, 80%, 100% { opacity: 0; }
    40%           { opacity: 1; }
  }
*/