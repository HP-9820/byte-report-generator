import React, { useEffect, useState } from 'react';

const History = ({ token }) => {
    const [reports, setReports] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [downloadingId, setDownloadingId] = useState(null);

    useEffect(() => {
        const fetchReports = async () => {
            try {
                const response = await fetch('http://localhost:8000/my-reports', {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });
                if (!response.ok) {
                    if (response.status === 401) throw new Error('Session expired. Please login again.');
                    throw new Error('Failed to fetch reports');
                }
                const data = await response.json();
                setReports(data);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        if (token) {
            fetchReports();
        }
    }, [token]);

    // FIXED: Download using the direct S3 URL
    const handleDownload = async (reportId, filename, downloadUrl) => {
        setDownloadingId(reportId);
        try {
            // Option 1: Direct download using window.open (simplest and works best)
            window.open(downloadUrl, '_blank');

            // Option 2: If you want to track download completion, use this:
            // const link = document.createElement('a');
            // link.href = downloadUrl;
            // link.download = filename;
            // document.body.appendChild(link);
            // link.click();
            // document.body.removeChild(link);

        } catch (err) {
            console.error('Download error:', err);
            alert('Failed to download file. Please try again.');
        } finally {
            setDownloadingId(null);
        }
    };

    return (
        <div className="w-full max-w-[1000px] mx-auto mt-10 animate-fadeIn space-y-8">
            <div className="text-center space-y-4">
                <h2 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-byte-green">My Generated Reports</h2>
                <p className="text-white/50 text-lg">View and redownload your previously generated class reports.</p>
            </div>

            <div className="glass-upload p-8 overflow-hidden rounded-3xl shadow-xl">
                {loading ? (
                    <div className="text-center text-white/50 font-bold py-10">Loading reports...</div>
                ) : error ? (
                    <div className="text-center text-red-400 font-bold py-10">{error}</div>
                ) : reports.length === 0 ? (
                    <div className="text-center text-white/50 font-bold py-10">No reports generated yet. Generate your first one!</div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="border-b border-white/10 text-white/40 text-xs tracking-widest uppercase">
                                    <th className="p-4 font-bold">Report Name</th>
                                    <th className="p-4 font-bold">Date Generated</th>
                                    <th className="p-4 font-bold text-right">Action</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {reports.map((report) => (
                                    <tr key={report.id} className="hover:bg-white/5 transition-colors group">
                                        <td className="p-4 font-medium text-white/90">{report.filename}</td>
                                        <td className="p-4 text-white/60 text-sm">
                                            {new Date(report.created_at).toLocaleString()}
                                        </td>
                                        <td className="p-4 text-right">
                                            <button
                                                onClick={() => handleDownload(report.id, report.filename, report.download_url)}
                                                disabled={downloadingId === report.id}
                                                className="text-byte-green font-bold text-sm tracking-wide hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                            >
                                                {downloadingId === report.id ? 'Opening...' : 'Download ↓'}
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
};

export default History;