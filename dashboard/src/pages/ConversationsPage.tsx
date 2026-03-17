import { useState } from 'react';
import { useConversations, useConversationDetail } from '../hooks/useConversations';
import { Search, MessageSquare, ArrowLeft, Clock } from 'lucide-react';
import { formatDate, timeAgo, clampText, statusColor } from '../lib/utils';
import { useClient } from '../contexts/ClientContext';

export default function ConversationsPage() {
  const { activeClient } = useClient();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { conversations, loading } = useConversations({
    search,
    status: statusFilter,
    page,
    page_size: 20,
    ...(activeClient?.id ? { client_id: activeClient.id } : {}),
  });

  const { detail, loading: detailLoading } = useConversationDetail(selectedId);

  // Detail view
  if (selectedId) {
    return (
      <div className="animate-fade-in">
        <button className="btn btn-ghost" onClick={() => setSelectedId(null)} style={{ marginBottom: 20 }}>
          <ArrowLeft size={16} /> Back to list
        </button>

        {detailLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><div className="spinner" /></div>
        ) : detail ? (
          <div className="glass-card" style={{ padding: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
              <div>
                <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Conversation</h2>
                <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: 4, fontFamily: 'monospace' }}>
                  {detail.session_id}
                </p>
              </div>
              <span className={`badge badge-${statusColor(detail.status)}`}>
                <span className={`status-dot ${statusColor(detail.status)}`} />
                {detail.status}
              </span>
            </div>

            <div style={{ display: 'flex', gap: 20, marginBottom: 24, fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <Clock size={14} /> {formatDate(detail.started_at)}
              </span>
              <span>{detail.message_count} messages</span>
              {detail.user_ip && <span>IP: {detail.user_ip}</span>}
              {detail.page_url && (
                <span style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  Page: <a href={detail.page_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--color-primary)' }}>{new URL(detail.page_url).pathname}</a>
                </span>
              )}
            </div>

            {/* Message thread */}
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
                  <div style={{ fontSize: '0.7rem', color: msg.role === 'user' ? 'rgba(255,255,255,0.5)' : 'var(--color-text-muted)', marginTop: 6, textAlign: 'right' }}>
                    {timeAgo(msg.created_at)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="empty-state">Conversation not found</div>
        )}
      </div>
    );
  }

  // List view
  return (
    <div className="animate-fade-in">
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 24 }}>
        <span className="gradient-text">Conversations</span>
      </h1>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
          <Search size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-muted)' }} />
          <input
            className="input"
            placeholder="Search messages..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            style={{ paddingLeft: 36 }}
          />
        </div>
        <select
          className="input"
          style={{ width: 160 }}
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="ended">Ended</option>
          <option value="escalated">Escalated</option>
        </select>
      </div>

      {/* Table */}
      <div className="glass-card" style={{ overflow: 'hidden' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><div className="spinner" /></div>
        ) : conversations.length === 0 ? (
          <div className="empty-state">
            <MessageSquare size={40} />
            <p style={{ marginTop: 8 }}>No conversations found</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Session</th>
                <th>Active Page</th>
                <th>Messages</th>
                <th>Status</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody>
              {conversations.map((c) => (
                <tr key={c.id} onClick={() => setSelectedId(c.id)}>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{clampText(c.session_id, 20)}</td>
                  <td style={{ maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {c.page_url ? <a href={c.page_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--color-primary)' }} onClick={(e) => e.stopPropagation()}>{new URL(c.page_url).pathname}</a> : '—'}
                  </td>
                  <td>{c.message_count}</td>
                  <td>
                    <span className={`badge badge-${statusColor(c.status)}`}>
                      <span className={`status-dot ${statusColor(c.status)}`} />
                      {c.status}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.8rem' }}>{timeAgo(c.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 20 }}>
        <button className="btn btn-ghost" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
          Previous
        </button>
        <span style={{ display: 'flex', alignItems: 'center', fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
          Page {page}
        </span>
        <button className="btn btn-ghost" disabled={conversations.length < 20} onClick={() => setPage((p) => p + 1)}>
          Next
        </button>
      </div>
    </div>
  );
}
