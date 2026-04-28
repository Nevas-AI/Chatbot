import { useState, useEffect } from 'react';
import { getLeads, getClients, Lead, Client } from '../lib/api';
import { useClient } from '../contexts/ClientContext';
import { Users, Mail, Phone, Building, Calendar, CheckCircle, XCircle, AlertCircle } from 'lucide-react';

export default function LeadsPage() {
    const { activeClient } = useClient();
    const [leads, setLeads] = useState<Lead[]>([]);
    const [clients, setClients] = useState<Client[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState<'all' | 'sent' | 'failed'>('all');

    useEffect(() => {
        loadLeads();
        loadClients();
    }, [activeClient?.id, filter]);

    const loadLeads = async () => {
        setLoading(true);
        try {
            const params: Record<string, string | number | boolean> = {};
            if (activeClient?.id) params.client_id = activeClient.id;
            if (filter === 'sent') params.email_sent = true;
            if (filter === 'failed') params.email_sent = false;
            const data = await getLeads(params);
            setLeads(data);
        } catch (err) {
            console.error('Failed to load leads:', err);
        } finally {
            setLoading(false);
        }
    };

    const loadClients = async () => {
        try {
            const data = await getClients();
            setClients(data);
        } catch (err) {
            console.error('Failed to load clients:', err);
        }
    };

    const getClientName = (clientId: string) => {
        const client = clients.find(c => c.id === clientId);
        return client?.company_name || client?.name || 'Unknown';
    };

    const formatDate = (dateStr: string) => {
        const d = new Date(dateStr);
        return d.toLocaleDateString('en-IN', {
            day: 'numeric', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    };

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                <div>
                    <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
                        <Users size={24} style={{ color: '#65bc47' }} /> Captured Leads
                    </h1>
                    <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', margin: '4px 0 0 0' }}>
                        Leads automatically captured by your chatbot from interested visitors.
                    </p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    {(['all', 'sent', 'failed'] as const).map(f => (
                        <button
                            key={f}
                            className="btn"
                            onClick={() => setFilter(f)}
                            style={{
                                background: filter === f ? '#65bc47' : 'var(--color-bg-secondary)',
                                color: filter === f ? '#fff' : 'var(--color-text)',
                                border: filter === f ? '1px solid #65bc47' : '1px solid var(--color-border)',
                                fontSize: '0.8rem',
                                padding: '6px 14px',
                                borderRadius: 8,
                                cursor: 'pointer',
                            }}
                        >
                            {f === 'all' ? 'All' : f === 'sent' ? '✅ Email Sent' : '⚠️ Not Sent'}
                        </button>
                    ))}
                </div>
            </div>

            {loading ? (
                <div style={{ textAlign: 'center', padding: 60, color: 'var(--color-text-muted)' }}>
                    Loading leads...
                </div>
            ) : leads.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 60 }}>
                    <AlertCircle size={48} style={{ color: 'var(--color-text-muted)', marginBottom: 12 }} />
                    <p style={{ color: 'var(--color-text-muted)', fontSize: '1rem' }}>
                        No leads captured yet. Leads will appear here when visitors express buying interest through the chatbot.
                    </p>
                </div>
            ) : (
                <div className="card" style={{ overflow: 'hidden' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                        <thead>
                            <tr style={{ borderBottom: '2px solid var(--color-border)', textAlign: 'left' }}>
                                <th style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--color-text-muted)' }}>Name</th>
                                <th style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--color-text-muted)' }}>Email</th>
                                <th style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--color-text-muted)' }}>Phone</th>
                                <th style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--color-text-muted)' }}>Company</th>
                                <th style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--color-text-muted)' }}>Client</th>
                                <th style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--color-text-muted)' }}>Email Status</th>
                                <th style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--color-text-muted)' }}>Captured</th>
                            </tr>
                        </thead>
                        <tbody>
                            {leads.map((lead) => (
                                <tr key={lead.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                                    <td style={{ padding: '12px 16px', fontWeight: 500 }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <Users size={14} style={{ color: '#65bc47' }} />
                                            {lead.name || <span style={{ color: 'var(--color-text-muted)', fontStyle: 'italic' }}>—</span>}
                                        </div>
                                    </td>
                                    <td style={{ padding: '12px 16px' }}>
                                        {lead.email ? (
                                            <a href={`mailto:${lead.email}`} style={{ color: '#65bc47', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
                                                <Mail size={14} /> {lead.email}
                                            </a>
                                        ) : (
                                            <span style={{ color: 'var(--color-text-muted)' }}>—</span>
                                        )}
                                    </td>
                                    <td style={{ padding: '12px 16px' }}>
                                        {lead.phone ? (
                                            <a href={`tel:${lead.phone}`} style={{ color: '#65bc47', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
                                                <Phone size={14} /> {lead.phone}
                                            </a>
                                        ) : (
                                            <span style={{ color: 'var(--color-text-muted)' }}>—</span>
                                        )}
                                    </td>
                                    <td style={{ padding: '12px 16px' }}>
                                        {lead.company ? (
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                                <Building size={14} style={{ color: 'var(--color-text-muted)' }} /> {lead.company}
                                            </div>
                                        ) : (
                                            <span style={{ color: 'var(--color-text-muted)' }}>—</span>
                                        )}
                                    </td>
                                    <td style={{ padding: '12px 16px', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                                        {getClientName(lead.client_id)}
                                    </td>
                                    <td style={{ padding: '12px 16px' }}>
                                        {lead.email_sent ? (
                                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#22c55e', fontSize: '0.8rem' }}>
                                                <CheckCircle size={14} /> Sent
                                            </span>
                                        ) : (
                                            <span
                                                style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#f59e0b', fontSize: '0.8rem', cursor: lead.email_error ? 'pointer' : 'default' }}
                                                title={lead.email_error || 'Email not configured or not sent'}
                                            >
                                                <XCircle size={14} /> Not Sent
                                            </span>
                                        )}
                                    </td>
                                    <td style={{ padding: '12px 16px', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                            <Calendar size={14} /> {formatDate(lead.created_at)}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}