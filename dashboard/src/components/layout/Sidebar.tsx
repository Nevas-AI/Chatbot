import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  MessageSquare,
  Radio,
  AlertTriangle,
  Users,
  UserPlus,
  Settings,
  Sparkles,
  Building2,
  ChevronDown,
  Share2,
} from 'lucide-react';
import { useClient } from '../../contexts/ClientContext';

const links = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/conversations', label: 'Conversations', icon: MessageSquare },
  { to: '/live', label: 'Live Chat', icon: Radio },
  { to: '/escalations', label: 'Escalations', icon: AlertTriangle },
  { to: '/users', label: 'Users', icon: Users },
  { to: '/leads', label: 'Leads', icon: UserPlus },
  { to: '/social', label: 'Social Media', icon: Share2 },
  { to: '/clients', label: 'Clients', icon: Building2 },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
  const { clients, activeClient, setActiveClientId } = useClient();

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div style={{ padding: '24px 20px 16px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Sparkles size={22} style={{ color: '#65bc47' }} />
        <span className="gradient-text" style={{ fontSize: '1.15rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
          Ascent IQ
        </span>
      </div>

      {/* Client Switcher */}
      {clients.length > 0 && (
        <div style={{ padding: '0 12px 16px' }}>
          <div
            style={{
              position: 'relative',
              background: 'var(--color-bg-secondary)',
              borderRadius: 10,
              border: '1px solid var(--color-border)',
            }}
          >
            <select
              value={activeClient?.id || ''}
              onChange={(e) => setActiveClientId(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 32px 10px 12px',
                background: 'transparent',
                border: 'none',
                color: 'var(--color-text)',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: 'pointer',
                appearance: 'none',
                outline: 'none',
                fontFamily: 'inherit',
              }}
            >
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <ChevronDown
              size={14}
              style={{
                position: 'absolute',
                right: 10,
                top: '50%',
                transform: 'translateY(-50%)',
                pointerEvents: 'none',
                color: 'var(--color-text-muted)',
              }}
            />
          </div>
        </div>
      )}

      {/* Nav links */}
      <nav style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '0 12px', flex: 1 }}>
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div style={{ padding: '16px 20px', borderTop: '1px solid var(--color-border)', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
        Ascent IQ v2.0
      </div>
    </aside>
  );
}
