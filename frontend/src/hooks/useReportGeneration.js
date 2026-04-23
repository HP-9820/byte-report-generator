// ─────────────────────────────────────────────────────────────
// useReportGeneration.js
// Drop this hook into your frontend/src/hooks/ folder
// ─────────────────────────────────────────────────────────────
//
// Usage:
//   import { useReportGeneration } from './hooks/useReportGeneration';
//
//   const { startGeneration, status, progress, total,
//           currentName, downloadUrl, error, reset } = useReportGeneration();
//
//   // To start:
//   await startGeneration(file, count, authToken);
//
// ─────────────────────────────────────────────────────────────

import { useState, useRef, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const POLL_INTERVAL_MS = 3000; // poll every 3 seconds

export function useReportGeneration() {
    const [status, setStatus] = useState('idle');   // idle | running | done | error
    const [progress, setProgress] = useState(0);
    const [total, setTotal] = useState(0);
    const [currentName, setCurrentName] = useState('');
    const [downloadUrl, setDownloadUrl] = useState(null);
    const [fileName, setFileName] = useState(null);
    const [error, setError] = useState(null);

    const pollerRef = useRef(null);

    // ── Stop polling ──
    const stopPolling = useCallback(() => {
        if (pollerRef.current) {
            clearInterval(pollerRef.current);
            pollerRef.current = null;
        }
    }, []);

    // ── Poll /job-status/{job_id} ──
    const startPolling = useCallback((jobId, token) => {
        pollerRef.current = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE}/job-status/${jobId}`, {
                    headers: { Authorization: `Bearer ${token}` },
                });

                if (!res.ok) {
                    stopPolling();
                    setStatus('error');
                    setError('Lost connection to server. Please refresh and check My Reports.');
                    return;
                }

                const data = await res.json();

                setProgress(data.progress ?? 0);
                setTotal(data.total ?? 0);
                setCurrentName(data.current_name ?? '');

                if (data.status === 'done') {
                    stopPolling();
                    setStatus('done');
                    setDownloadUrl(data.result?.download_url ?? null);
                    setFileName(data.result?.file_name ?? null);
                } else if (data.status === 'error') {
                    stopPolling();
                    setStatus('error');
                    setError(data.error ?? 'An unknown error occurred.');
                }
                // else still running – keep polling
            } catch (err) {
                console.error('Polling error:', err);
                // Don't stop on network blips – try again next tick
            }
        }, POLL_INTERVAL_MS);
    }, [stopPolling]);

    // ── Kick off generation ──
    const startGeneration = useCallback(async (file, count, token) => {
        // Reset state
        setStatus('running');
        setProgress(0);
        setTotal(0);
        setCurrentName('');
        setDownloadUrl(null);
        setFileName(null);
        setError(null);
        stopPolling();

        try {
            const formData = new FormData();
            formData.append('file', file);
            if (count) formData.append('count', count);

            const res = await fetch(`${API_BASE}/generate-reports`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${token}` },
                body: formData,
            });

            const data = await res.json();

            if (!res.ok) {
                setStatus('error');
                setError(data.detail ?? 'Failed to start generation.');
                return;
            }

            // Backend returns 202 + job_id immediately
            const { job_id, total: jobTotal } = data;
            setTotal(jobTotal ?? 0);

            // Begin polling
            startPolling(job_id, token);
        } catch (err) {
            setStatus('error');
            setError(err.message ?? 'Network error. Please try again.');
        }
    }, [startPolling, stopPolling]);

    // ── Reset to idle ──
    const reset = useCallback(() => {
        stopPolling();
        setStatus('idle');
        setProgress(0);
        setTotal(0);
        setCurrentName('');
        setDownloadUrl(null);
        setFileName(null);
        setError(null);
    }, [stopPolling]);

    return {
        startGeneration,
        status,        // 'idle' | 'running' | 'done' | 'error'
        progress,      // number of students done
        total,         // total students
        currentName,   // name currently being processed
        downloadUrl,   // S3 URL when done
        fileName,      // docx filename when done
        error,         // error message string when failed
        reset,         // call to go back to idle
    };
}