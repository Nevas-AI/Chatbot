import { useState, useEffect } from 'react';
import { getUsers, getUser, type ChatUser, type ChatUserDetail } from '../lib/api';
import { Search, Users, ArrowLeft, Monitor, Smartphone, Tablet, Clock, MessageSquare, Globe, Tag, Save } from 'lucide-react';
import { formatDate, timeAgo, statusColor } from '../lib/utils';
import { updateUserTags } from '../lib/api';
import { useClient } from '../contexts/ClientContext';

export default function UsersPage() {
  const { activeClient } = useClient();
  const [users, setUsers] = useState<ChatUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [deviceFilter, setDeviceFilter] = useState('');
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ChatUserDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [tagInput, setTagInput] = useState('');
  const [tagSaving, setTagSaving] = useState(false);

  // Fetch user list
  useEffect(() => {
    setLoading(true);
    getUsers({
      search,
      device_type: deviceFilter,
      page,
      page_size: 20,
      ...(activeClient?.id ? { client_id: activeClient.id } : {}),
    })
      .then(setUsers)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [search, deviceFilter, page]);

  // Fetch user detail
  useEffect(() => {
    if (!selectedId) { setDetail(null); return; }
    setDetailLoading(true);
    getUser(selectedId)
      .then((d) => {
        setDetail(d);
        setTagInput(d.tags ? Object.entries(d.tags).map(([k, v]) => `${k}: ${v}`).join(', ') : '');
      })
      .catch(console.error)
      .finally(() => setDetailLoading(false));
  }, [selectedId]);

  const deviceIcon = (type: string | null) => {
    switch (type) {
      case 'mobile': return <Smartphone size={14} />;
      case 'tablet': return <Tablet size={14} />;
      default: return <Monitor size={14} />;
    }
  };

  const handleSaveTags = async () => {
    if (!selectedId || !detail) return;
    setTagSaving(true);
    try {
      const tags: Record<string, string> = {};
      tagInput.split(',').forEach((pair) => {
        const [key, ...rest] = pair.split(':');
        if (key?.trim()) tags[key.trim()] = rest.join(':').trim();
      });
      await updateUserTags(selectedId, tags);
      setDetail({ ...detail, tags });
    } catch (err) { console.error(err); }
    finally { setTagSaving(false); }
  };

  // ─── Detail View ───
  if (selectedId) {
    return (
      <div className="animate-fade-in">
        <button className="btn btn-ghost" onClick={() => setSelectedId(null)} style={{ marginBottom: 20 }}>
          <ArrowLeft size={16} /> Back to users
        </button>

        {detailLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><div className="spinner" /></div>
        ) : detail ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            {/* Left: User Info */}
            <div className="glass-card" style={{ padding: 24 }}>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 20 }}>User Profile</h2>

              <div style={{ display: 'grid', gap: 16 }}>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                  <Globe size={16} style={{ color: 'var(--color-accent)' }} />
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>IP Address</div>
                    <div style={{ fontFamily: 'monospace' }}>{detail.ip_address || '—'}</div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                  {deviceIcon(detail.device_type)}
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Device</div>
                    <div>{detail.browser || '—'} · {detail.os || '—'} · {detail.device_type || '—'}</div>
                  </div>
                </div>

                {(detail.city || detail.country) && (
                  <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                    <Globe size={16} style={{ color: 'var(--color-accent)' }} />
                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Location</div>
                      <div>{[detail.city, detail.country].filter(Boolean).join(', ')}</div>
                    </div>
                  </div>
                )}

                <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                  <Clock size={16} style={{ color: 'var(--color-accent)' }} />
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Activity</div>
                    <div style={{ fontSize: '0.85rem' }}>
                      First seen: {formatDate(detail.first_seen)}<br />
                      Last seen: {timeAgo(detail.last_seen)}
                    </div>
                  </div>
                </div>

                {detail.last_page && (
                  <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                    <Monitor size={16} style={{ color: 'var(--color-accent)' }} />
                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Active Page</div>
                      <div style={{ fontSize: '0.85rem', wordBreak: 'break-all' }}>
                        <a href={detail.last_page} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--color-primary)' }}>
                          {detail.last_page}
                        </a>
                      </div>
                    </div>
                  </div>
                )}

                <div style={{ display: 'flex', gap: 24 }}>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Conversations</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{detail.total_conversations}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Messages</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{detail.total_messages}</div>
                  </div>
                </div>

                {/* Tags editor */}
                <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                    <Tag size={14} style={{ color: 'var(--color-accent)' }} />
                    <span style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--color-text-muted)' }}>Tags / Notes</span>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input
                      className="input"
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      placeholder="key: value, key: value"
                      style={{ flex: 1 }}
                    />
                    <button className="btn btn-primary" onClick={handleSaveTags} disabled={tagSaving}>
                      <Save size={14} /> {tagSaving ? '...' : 'Save'}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Right: Conversation History */}
            <div className="glass-card" style={{ padding: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
                <MessageSquare size={16} style={{ color: 'var(--color-accent)' }} />
                <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Interaction History</h2>
                <span className="badge badge-active" style={{ marginLeft: 'auto' }}>
                  {detail.conversations.length} total
                </span>
              </div>

              {detail.conversations.length === 0 ? (
                <div className="empty-state">
                  <MessageSquare size={36} />
                  <p style={{ marginTop: 8 }}>No conversations yet</p>
                </div>
              ) : (
                <div style={{ maxHeight: 460, overflowY: 'auto' }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Session</th>
                        <th>Messages</th>
                        <th>Status</th>
                        <th>Started</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.conversations.map((c) => (
                        <tr key={c.id}>
                          <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{c.session_id.slice(0, 12)}…</td>
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
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="empty-state">User not found</div>
        )}
      </div>
    );
  }

  // ─── List View ───
  return (
    <div className="animate-fade-in">
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 24 }}>
        <span className="gradient-text">Users</span>
      </h1>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
          <Search size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-muted)' }} />
          <input
            className="input"
            placeholder="Search by IP, browser, location..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            style={{ paddingLeft: 36 }}
          />
        </div>
        <select
          className="input"
          style={{ width: 160 }}
          value={deviceFilter}
          onChange={(e) => { setDeviceFilter(e.target.value); setPage(1); }}
        >
          <option value="">All devices</option>
          <option value="desktop">Desktop</option>
          <option value="mobile">Mobile</option>
          <option value="tablet">Tablet</option>
        </select>
      </div>

      {/* Table */}
      <div className="glass-card" style={{ overflow: 'hidden' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><div className="spinner" /></div>
        ) : users.length === 0 ? (
          <div className="empty-state">
            <Users size={40} />
            <p style={{ marginTop: 8 }}>No users found</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>IP Address</th>
                <th>Device</th>
                <th>Location</th>
                <th>Active Page</th>
                <th>Conversations</th>
                <th>Messages</th>
                <th>Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} onClick={() => setSelectedId(u.id)}>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{u.ip_address || '—'}</td>
                  <td>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {deviceIcon(u.device_type)}
                      {u.device_type || '—'}
                    </span>
                  </td>
                  <td>{[u.city, u.country].filter(Boolean).join(', ') || '—'}</td>
                  <td style={{ maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {u.last_page ? <a href={u.last_page} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--color-primary)' }}>{new URL(u.last_page).pathname}</a> : '—'}
                  </td>
                  <td>{u.total_conversations}</td>
                  <td>{u.total_messages}</td>
                  <td style={{ fontSize: '0.8rem' }}>{timeAgo(u.last_seen)}</td>
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
        <button className="btn btn-ghost" disabled={users.length < 20} onClick={() => setPage((p) => p + 1)}>
          Next
        </button>
      </div>
    </div>
  );
}
