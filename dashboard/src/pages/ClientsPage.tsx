import { useState, useEffect } from 'react';
import { createClient, updateClient, deleteClient, Client, ClientCreateInput } from '../lib/api';
import { useClient } from '../contexts/ClientContext';
import { Plus, Edit2, Trash2, Globe, Mail, Phone, Clock, Palette, Save, X } from 'lucide-react';

const emptyForm: ClientCreateInput = {
  name: '',
  slug: '',
  bot_name: 'Neva',
  primary_color: '#6366F1',
  welcome_msg: '',
  logo_url: '',
  company_name: '',
  support_email: '',
  support_phone: '',
  business_hours: 'Mon-Fri 9AM-6PM IST',
  website_url: '',
  collection_name: '',
};

export default function ClientsPage() {
  const { clients, refreshClients } = useClient();
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ClientCreateInput>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (key: string, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleCreate = async () => {
    if (!form.name || !form.slug) {
      setError('Name and Slug are required');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await createClient(form);
      await refreshClients();
      setShowForm(false);
      setForm(emptyForm);
    } catch (err: any) {
      setError(err.message || 'Failed to create client');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async () => {
    if (!editingId) return;
    setSaving(true);
    setError('');
    try {
      await updateClient(editingId, form);
      await refreshClients();
      setEditingId(null);
      setShowForm(false);
      setForm(emptyForm);
    } catch (err: any) {
      setError(err.message || 'Failed to update client');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to deactivate this client?')) return;
    try {
      await deleteClient(id);
      await refreshClients();
    } catch (err: any) {
      setError(err.message || 'Failed to delete client');
    }
  };

  const startEdit = (client: Client) => {
    setEditingId(client.id);
    setForm({
      name: client.name,
      slug: client.slug,
      bot_name: client.bot_name,
      primary_color: client.primary_color,
      welcome_msg: client.welcome_msg || '',
      logo_url: client.logo_url || '',
      company_name: client.company_name,
      support_email: client.support_email,
      support_phone: client.support_phone,
      business_hours: client.business_hours,
      website_url: client.website_url || '',
      collection_name: client.collection_name,
    });
    setShowForm(true);
  };

  const cancelForm = () => {
    setShowForm(false);
    setEditingId(null);
    setForm(emptyForm);
    setError('');
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 4 }}>Clients</h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
            Manage client tenants — each client has isolated data, branding, and knowledge bases.
          </p>
        </div>
        {!showForm && (
          <button className="btn btn-primary" onClick={() => { setShowForm(true); setEditingId(null); setForm(emptyForm); }}>
            <Plus size={16} /> New Client
          </button>
        )}
      </div>

      {error && (
        <div className="card" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', marginBottom: 16, padding: '12px 16px', color: '#ef4444' }}>
          {error}
        </div>
      )}

      {showForm && (
        <div className="card" style={{ marginBottom: 24, padding: 24 }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 20 }}>
            {editingId ? 'Edit Client' : 'Create New Client'}
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                Client Name *
              </label>
              <input className="input" value={form.name} onChange={(e) => handleChange('name', e.target.value)} placeholder="Acme Corp" />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                Slug * <span style={{ fontWeight: 400 }}>(URL-safe ID, lowercase)</span>
              </label>
              <input
                className="input"
                value={form.slug}
                onChange={(e) => handleChange('slug', e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ''))}
                placeholder="acme-corp"
                disabled={!!editingId}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                Company Name
              </label>
              <input className="input" value={form.company_name} onChange={(e) => handleChange('company_name', e.target.value)} placeholder="Acme Corporation" />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                Bot Name
              </label>
              <input className="input" value={form.bot_name} onChange={(e) => handleChange('bot_name', e.target.value)} placeholder="Neva" />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                <Palette size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Primary Color
              </label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input type="color" value={form.primary_color} onChange={(e) => handleChange('primary_color', e.target.value)} style={{ width: 40, height: 36, border: 'none', cursor: 'pointer' }} />
                <input className="input" value={form.primary_color} onChange={(e) => handleChange('primary_color', e.target.value)} style={{ flex: 1 }} />
              </div>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                <Globe size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Website URL
              </label>
              <input className="input" value={form.website_url} onChange={(e) => handleChange('website_url', e.target.value)} placeholder="https://example.com" />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                <Mail size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Support Email
              </label>
              <input className="input" value={form.support_email} onChange={(e) => handleChange('support_email', e.target.value)} placeholder="support@acme.com" />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                <Phone size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Support Phone
              </label>
              <input className="input" value={form.support_phone} onChange={(e) => handleChange('support_phone', e.target.value)} placeholder="+91-XXXXXXXXXX" />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                <Clock size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Business Hours
              </label>
              <input className="input" value={form.business_hours} onChange={(e) => handleChange('business_hours', e.target.value)} placeholder="Mon-Fri 9AM-6PM IST" />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                Collection Name <span style={{ fontWeight: 400 }}>(auto from slug if empty)</span>
              </label>
              <input className="input" value={form.collection_name} onChange={(e) => handleChange('collection_name', e.target.value)} placeholder="acme_knowledge" />
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                Welcome Message
              </label>
              <textarea
                className="input"
                value={form.welcome_msg}
                onChange={(e) => handleChange('welcome_msg', e.target.value)}
                placeholder="Hi there! 👋 How can I help you today?"
                rows={2}
                style={{ resize: 'vertical' }}
              />
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                Logo URL
              </label>
              <input className="input" value={form.logo_url} onChange={(e) => handleChange('logo_url', e.target.value)} placeholder="https://example.com/logo.png" />
            </div>
          </div>
          <div style={{ display: 'flex', gap: 12, marginTop: 20, justifyContent: 'flex-end' }}>
            <button className="btn" onClick={cancelForm}>
              <X size={16} /> Cancel
            </button>
            <button className="btn btn-primary" onClick={editingId ? handleUpdate : handleCreate} disabled={saving}>
              <Save size={16} /> {saving ? 'Saving...' : editingId ? 'Update' : 'Create'}
            </button>
          </div>
        </div>
      )}

      {/* Client cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: 16 }}>
        {clients.map((client) => (
          <div key={client.id} className="card" style={{ padding: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 32, height: 32, borderRadius: '50%', background: client.primary_color, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 700, fontSize: '0.8rem' }}>
                  {client.name.charAt(0).toUpperCase()}
                </div>
                <div>
                  <div style={{ fontWeight: 600 }}>{client.name}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>/{client.slug}</div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <button className="btn" style={{ padding: '6px 8px' }} onClick={() => startEdit(client)} title="Edit">
                  <Edit2 size={14} />
                </button>
                <button className="btn" style={{ padding: '6px 8px', color: '#ef4444' }} onClick={() => handleDelete(client.id)} title="Deactivate">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px' }}>
              <div>🤖 {client.bot_name}</div>
              <div>🏢 {client.company_name}</div>
              <div>📧 {client.support_email}</div>
              <div>📞 {client.support_phone}</div>
              <div>🕐 {client.business_hours}</div>
              {client.website_url && <div>🌐 {client.website_url}</div>}
            </div>
            <div style={{ marginTop: 12, fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>
              Widget embed: <code style={{ background: 'var(--color-bg-secondary)', padding: '2px 6px', borderRadius: 4 }}>clientId: "{client.slug}"</code>
            </div>
          </div>
        ))}
      </div>

      {clients.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: 48, color: 'var(--color-text-muted)' }}>
          No clients yet. Click "New Client" to create one.
        </div>
      )}
    </div>
  );
}
