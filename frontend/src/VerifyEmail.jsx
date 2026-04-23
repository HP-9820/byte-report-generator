import React, { useEffect, useState } from 'react';

const VerifyEmail = () => {
    const [status, setStatus] = useState({ type: 'info', message: 'Verifying your email...' });

    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const token = params.get('token');

        if (!token) {
            setStatus({ type: 'error', message: 'No verification token provided.' });
            return;
        }

        const verifyToken = async () => {
            try {
                const response = await fetch(`http://localhost:8000/verify-email?token=${token}`);
                const data = await response.json();
                if (response.ok) {
                    setStatus({ type: 'success', message: data.message || 'Email verified successfully!' });
                } else {
                    setStatus({ type: 'error', message: data.detail || 'Verification failed.' });
                }
            } catch (err) {
                setStatus({ type: 'error', message: 'Network error. Backend might be down.' });
            }
        };

        verifyToken();
    }, []);

    return (
        <div className="min-h-screen flex items-center justify-center p-6 relative z-10 w-full mt-10">
            <div className="glass-upload p-12 w-full max-w-[450px] space-y-8 animate-fadeIn text-center border border-white/10 rounded-3xl shadow-2xl">
                <img src="/normalImage.png" alt="ByTE Logo" className="w-16 h-16 mx-auto mb-4 drop-shadow-md" />
                <h2 className="text-3xl font-bold tracking-tight text-white/90">Email Verification</h2>

                <div className={`p-4 rounded-xl text-sm font-bold ${status.type === 'success' ? 'bg-byte-green/20 text-byte-green border border-byte-green/30' : status.type === 'error' ? 'bg-red-500/20 text-red-500 border border-red-500/30' : 'bg-blue-500/20 text-blue-400 border border-blue-500/30'}`}>
                    {status.message}
                </div>

                <button
                    onClick={() => window.location.href = '/'}
                    className="btn-green w-full py-4 text-base shadow-[0_5px_20px_rgba(118,200,89,0.2)] mt-6"
                >
                    Return to Login
                </button>
            </div>
        </div>
    );
};

export default VerifyEmail;