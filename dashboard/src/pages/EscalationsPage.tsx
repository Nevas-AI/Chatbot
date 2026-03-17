import { useState, useEffect } from 'react';
import { getEscalations, resolveEscalation, type Escalation } from '../lib/api';
import { AlertTriangle, UserCheck, CheckCircle, Clock } from 'lucide-react';
import { timeAgo, statusColor } from '../lib/utils';
import { useClient } from '../contexts/ClientContext';

export default function EscalationsPage() {
  const { activeClient } = useClient();
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');

  const fetchEscalations = async () => {
    setLoading(true);
    try {
      const data = await getEscalations({
        status: filter,
        ...(activeClient?.id ? { client_id: activeClient.id } : {}),
      });
      setEscalations(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchEscalations(); }, [filter]);

  const handleResolve = async (id: string) => {
    try {
      await resolveEscalation(id);
      fetchEscalations();
    } catch (err) { console.error(err); }
  };

  return (
    <div className="animate-fade-in">
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 24 }}>
        <span className="gradient-text">Escalations</span>
      </h1>

      {/* Filter */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {['', 'pending', 'assigned', 'resolved'].map((s) => (
          <button
            key={s}
            className={`btn ${filter === s ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setFilter(s)}
          >
            {s || 'All'}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><div className="spinner" /></div>
      ) : escalations.length === 0 ? (
        <div className="glass-card">
          <div className="empty-state">
            <AlertTriangle size={48} />
            <p style={{ marginTop: 12 }}>No escalations found</p>
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 16 }}>
          {escalations.map((esc) => (
            <div key={esc.id} className="glass-card animate-slide-in" style={{ padding: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <AlertTriangle size={16} style={{ color: 'var(--color-danger)' }} />
                    <span style={{ fontWeight: 600 }}>Trigger: {esc.trigger_keyword}</span>
                    <span className={`badge badge-${statusColor(esc.status)}`}>
                      <span className={`status-dot ${statusColor(esc.status)}`} />
                      {esc.status}
                    </span>
                  </div>

                  <div style={{ display: 'flex', gap: 16, fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Clock size={12} /> {timeAgo(esc.created_at)}
                    </span>
                    {esc.resolved_at && (
                      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <CheckCircle size={12} /> Resolved {timeAgo(esc.resolved_at)}
                      </span>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  {(esc.status === 'pending' || esc.status === 'assigned') && (
                    <button className="btn btn-success" onClick={() => handleResolve(esc.id)}>
                      <CheckCircle size={14} /> Resolve
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
