import React, { useState } from 'react';

const Auth = ({ onLogin }) => {
    const [isRegister, setIsRegister] = useState(false);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [status, setStatus] = useState({ type: '', message: '' });
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setStatus({ type: '', message: '' });

        try {
            if (isRegister) {
                const response = await fetch('http://localhost:8000/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password })
                });
                const data = await response.json();

                if (response.ok) {
                    setStatus({ type: 'success', message: data.message || 'Registration successful! You can now log in.' });
                    setIsRegister(false);
                } else {
                    setStatus({ type: 'error', message: data.detail || 'Registration failed' });
                }
            } else {
                const formData = new URLSearchParams();
                formData.append('username', email); // OAuth2 expects 'username' field, we pass email
                formData.append('password', password);

                const response = await fetch('http://localhost:8000/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData
                });
                const data = await response.json();

                if (response.ok) {
                    localStorage.setItem('token', data.access_token);
                    onLogin(data.access_token);
                } else {
                    setStatus({ type: 'error', message: data.detail || 'Login failed' });
                }
            }
        } catch (err) {
            setStatus({ type: 'error', message: 'Network error. Backend might be down.' });
        }
        setLoading(false);
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-6 relative z-10 w-full">
            <div className="glass-upload p-12 w-full max-w-[450px] space-y-8 animate-fadeIn mt-10">
                <div className="text-center space-y-2">
                    <img src="/normalImage.png" alt="ByTE Logo" className="w-16 h-16 mx-auto mb-4 drop-shadow-md" />
                    <h2 className="text-3xl font-bold tracking-tight text-white/90">
                        {isRegister ? 'Create Account' : 'Welcome Back'}
                    </h2>
                    <p className="text-white/50 text-sm">
                        {isRegister ? 'Sign up to generate reports' : 'Login to access the Report Generator'}
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6">
                    <div className="space-y-2">
                        <label className="text-xs font-bold uppercase tracking-widest text-white/40 ml-1">Email Address</label>
                        <input
                            type="email"
                            required
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full bg-white/5 border border-white/10 rounded-xl px-5 py-3 focus:outline-none focus:border-byte-green transition-colors text-white"
                        />
                    </div>
                    <div className="space-y-2">
                        <label className="text-xs font-bold uppercase tracking-widest text-white/40 ml-1">Password</label>
                        <input
                            type="password"
                            required
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full bg-white/5 border border-white/10 rounded-xl px-5 py-3 focus:outline-none focus:border-byte-green transition-colors text-white"
                        />
                    </div>

                    {status.message && (
                        <div className={`p-3 rounded-lg text-sm font-bold text-center ${status.type === 'success' ? 'bg-byte-green/20 text-byte-green' : 'bg-red-500/20 text-red-500'}`}>
                            {status.message}
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={loading}
                        className="btn-green w-full py-4 text-base shadow-[0_5px_20px_rgba(118,200,89,0.2)] disabled:opacity-50"
                    >
                        {loading ? 'Processing...' : (isRegister ? 'Sign Up' : 'Sign In')}
                    </button>
                </form>

                <div className="text-center">
                    <button
                        onClick={() => {
                            setIsRegister(!isRegister);
                            setStatus({ type: '', message: '' });
                        }}
                        className="text-white/40 hover:text-white transition-colors text-sm underline-offset-4 hover:underline"
                    >
                        {isRegister ? 'Already have an account? Sign In' : "Don't have an account? Sign Up"}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default Auth;