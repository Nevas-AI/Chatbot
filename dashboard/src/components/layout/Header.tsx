import { useWebSocket } from '../../hooks/useWebSocket';
import { Wifi, WifiOff } from 'lucide-react';

const WS_URL = `${(import.meta.env.VITE_API_URL || 'http://localhost:8000').replace('http', 'ws')}/api/dashboard/ws/live`;

export default function Header() {
  const { connected } = useWebSocket(WS_URL);

  return (
    <header
      style={{
        height: 60,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 28px',
        borderBottom: '1px solid var(--color-border)',
        background: 'rgba(10, 14, 26, 0.6)',
        backdropFilter: 'blur(12px)',
        position: 'sticky',
        top: 0,
        zIndex: 30,
      }}
    >
      <div style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
        Conversation Monitoring
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {connected ? (
          <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--color-success)', fontSize: '0.8rem' }}>
            <Wifi size={14} /> Live
          </span>
        ) : (
          <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--color-danger)', fontSize: '0.8rem' }}>
            <WifiOff size={14} /> Offline
          </span>
        )}
        <button
          onClick={() => {
            localStorage.removeItem('auth_token');
            window.location.reload();
          }}
          style={{
            marginLeft: '16px',
            padding: '6px 12px',
            background: 'var(--color-bg-secondary)',
            color: 'var(--color-text)',
            border: '1px solid var(--color-border)',
            borderRadius: '6px',
            fontSize: '13px',
            cursor: 'pointer'
          }}
        >
          Logout
        </button>
      </div>
    </header>
  );
}
