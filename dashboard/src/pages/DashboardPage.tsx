import { useStats } from '../hooks/useStats';
import { useActiveConversations } from '../hooks/useConversations';
import {
  MessageSquare,
  Radio,
  AlertTriangle,
  TrendingUp,
  Calendar,
  Users,
  BarChart3,
} from 'lucide-react';
import { timeAgo, clampText, statusColor } from '../lib/utils';
import { useNavigate } from 'react-router-dom';
import { useClient } from '../contexts/ClientContext';

export default function DashboardPage() {
  const { activeClient } = useClient();
  const { stats, loading: statsLoading } = useStats(activeClient?.id);
  const { conversations: active, loading: activeLoading } = useActiveConversations(activeClient?.id);
  const navigate = useNavigate();

  const cards = stats
    ? [
      { label: 'Total Conversations', value: stats.total_conversations, icon: MessageSquare, color: '#65bc47' },
      { label: 'Active Now', value: stats.active_conversations, icon: Radio, color: '#22c55e' },
      { label: 'Escalations Today', value: stats.escalations_today, icon: AlertTriangle, color: '#ef4444' },
      { label: 'Avg Messages', value: stats.avg_messages_per_conversation, icon: TrendingUp, color: '#f59e0b' },
      { label: 'Today\'s Convos', value: stats.conversations_today, icon: Calendar, color: '#3b82f6' },
      { label: 'Total Users', value: stats.total_users, icon: Users, color: '#8b5cf6' },
    ]
    : [];

  return (
    <div className="animate-fade-in">
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 24 }}>
        <span className="gradient-text">Dashboard Overview</span>
      </h1>

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 16, marginBottom: 32 }}>
        {statsLoading
          ? Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="glass-card" style={{ padding: 24, height: 110 }}>
              <div className="spinner" />
            </div>
          ))
          : cards.map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="glass-card" style={{ padding: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}>
                    {label}
                  </div>
                  <div style={{ fontSize: '1.75rem', fontWeight: 700 }}>{value}</div>
                </div>
                <div style={{ background: `${color}20`, borderRadius: 10, padding: 10 }}>
                  <Icon size={20} style={{ color }} />
                </div>
              </div>
            </div>
          ))}
      </div>

      {/* Active Conversations */}
      <div className="glass-card" style={{ padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
          <BarChart3 size={18} style={{ color: 'var(--color-accent)' }} />
          <h2 style={{ fontSize: '1.05rem', fontWeight: 600 }}>Active Conversations</h2>
          {!activeLoading && (
            <span className="badge badge-active" style={{ marginLeft: 'auto' }}>
              {active.length} live
            </span>
          )}
        </div>

        {activeLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><div className="spinner" /></div>
        ) : active.length === 0 ? (
          <div className="empty-state">
            <Radio size={40} />
            <p style={{ marginTop: 8 }}>No active conversations right now</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Session</th>
                <th>IP</th>
                <th>Messages</th>
                <th>Started</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {active.map((c) => (
                <tr key={c.id} onClick={() => navigate(`/conversations/${c.id}`)}>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{clampText(c.session_id, 16)}</td>
                  <td>{c.user_ip || '—'}</td>
                  <td>{c.message_count}</td>
                  <td>{timeAgo(c.started_at)}</td>
                  <td><span className={`badge badge-${statusColor(c.status)}`}><span className={`status-dot ${statusColor(c.status)}`} />{c.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
