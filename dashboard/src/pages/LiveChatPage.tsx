import { useEffect, useState } from 'react';
import { useActiveConversations, useConversationDetail } from '../hooks/useConversations';
import { useWebSocket } from '../hooks/useWebSocket';
import { Radio, ArrowLeft, Clock } from 'lucide-react';
import { timeAgo, clampText, statusColor, formatDate } from '../lib/utils';
import { useClient } from '../contexts/ClientContext';

const WS_URL = `${(import.meta.env.VITE_API_URL || 'http://localhost:8000').replace('http', 'ws')}/api/dashboard/ws/live`;

export default function LiveChatPage() {
  const { activeClient } = useClient();
  const { conversations, loading, refresh } = useActiveConversations(activeClient?.id);
  const { events } = useWebSocket(WS_URL);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { detail, loading: detailLoading, refresh: refreshDetail } = useConversationDetail(selectedId);

  // Auto-refresh on new WebSocket events
  useEffect(() => {
    const last = events[events.length - 1];
    if (last && (last.type === 'new_message' || last.type === 'new_escalation')) {
      refresh();
      if (selectedId) refreshDetail();
    }
  }, [events, refresh, selectedId, refreshDetail]);

  if (selectedId) {
    return (
      <div className="animate-fade-in">
        <button className="btn btn-ghost" onClick={() => setSelectedId(null)} style={{ marginBottom: 20 }}>
          <ArrowLeft size={16} /> Back to live view
        </button>

        {detailLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><div className="spinner" /></div>
        ) : detail ? (
          <div className="glass-card" style={{ padding: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
              <div>
                <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Live Conversation</h2>
                <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', fontFamily: 'monospace', marginTop: 4 }}>
                  {detail.session_id}
                </p>
              </div>
              <span className="badge badge-active animate-pulse-glow">
                <span className="status-dot active" /> Live
              </span>
            </div>

            <div style={{ display: 'flex', gap: 16, fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: 20 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Clock size={14} /> {formatDate(detail.started_at)}</span>
              <span>{detail.message_count} messages</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 500, overflowY: 'auto', padding: 8 }}>
              {detail.messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`chat-bubble ${msg.role}`}
                  style={msg.role === 'user' ? { alignSelf: 'flex-end' } : { alignSelf: 'flex-start' }}
                >
                  <div style={{ fontSize: '0.7rem', color: msg.role === 'user' ? 'rgba(255,255,255,0.7)' : 'var(--color-text-muted)', marginBottom: 4, fontWeight: 600, textTransform: 'uppercase' }}>
                    {msg.role}
                  </div>
                  <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>
          <span className="gradient-text">Live Chat</span>
        </h1>
        <span className="badge badge-active" style={{ marginLeft: 8 }}>
          <span className="status-dot active" /> {conversations.length} active
        </span>
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><div className="spinner" /></div>
      ) : conversations.length === 0 ? (
        <div className="glass-card">
          <div className="empty-state">
            <Radio size={48} />
            <p style={{ marginTop: 12, fontSize: '1rem' }}>No active conversations</p>
            <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
              Conversations will appear here in real-time as users chat with Aria
            </p>
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
          {conversations.map((c) => (
            <div
              key={c.id}
              className="glass-card animate-slide-in"
              style={{ padding: 20, cursor: 'pointer' }}
              onClick={() => setSelectedId(c.id)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                <span style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                  {clampText(c.session_id, 16)}
                </span>
                <span className={`badge badge-${statusColor(c.status)}`}>
                  <span className={`status-dot ${statusColor(c.status)}`} />
                  {c.status}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
                <span>{c.message_count} messages</span>
                <span>{timeAgo(c.started_at)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
