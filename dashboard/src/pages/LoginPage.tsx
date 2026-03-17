import { useState } from 'react';

interface LoginPageProps {
  onLogin: () => void;
}

export default function LoginPage({ onLogin }: LoginPageProps) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // For simple internal use, we check against a fixed password or send to backend
      const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/dashboard/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });

      if (!res.ok) {
        throw new Error('Invalid internal access code');
      }

      const data = await res.json();
      localStorage.setItem('auth_token', data.token);
      onLogin();
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      background: 'var(--color-bg-primary)',
      fontFamily: 'Inter, sans-serif'
    }}>
      <div style={{
        background: 'var(--color-bg-secondary)',
        padding: '40px',
        borderRadius: '12px',
        border: '1px solid var(--color-border)',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
        width: '100%',
        maxWidth: '400px',
        textAlign: 'center'
      }}>
        <h1 style={{ color: 'var(--color-text)', marginBottom: '8px', fontSize: '24px' }}>Dashboard Login</h1>
        <p style={{ color: 'var(--color-text-muted)', marginBottom: '32px', fontSize: '14px' }}>Internal Access Only</p>
        
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <input
              type="password"
              placeholder="Enter access code..."
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{
                width: '100%',
                padding: '12px 16px',
                background: 'var(--color-bg-primary)',
                border: '1px solid var(--color-border)',
                borderRadius: '8px',
                color: 'var(--color-text)',
                outline: 'none',
                fontSize: '15px'
              }}
              required
            />
          </div>

          {error && (
            <div style={{ color: 'var(--color-danger)', fontSize: '14px', background: 'rgba(239, 68, 68, 0.1)', padding: '8px', borderRadius: '4px' }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '12px',
              background: 'var(--color-primary)',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              fontSize: '15px',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
              transition: 'opacity 0.2s',
            }}
          >
            {loading ? 'Authenticating...' : 'Access Dashboard'}
          </button>
        </form>
      </div>
    </div>
  );
}
