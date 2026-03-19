import { useState, useEffect, useRef } from 'react';
import { createClient, updateClient, deleteClient, testClientEmail, uploadClientLogo, deleteClientLogo, Client, ClientCreateInput } from '../lib/api';
import { useClient } from '../contexts/ClientContext';
import { Plus, Edit2, Trash2, Globe, Mail, Phone, Clock, Palette, Save, X, Send, Lock, ToggleLeft, ToggleRight, Upload, Image } from 'lucide-react';

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
  lead_email: '',
  lead_email_password: '',
  email_enabled: false,
};

export default function ClientsPage() {
  const { clients, refreshClients } = useClient();
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ClientCreateInput>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [testingEmail, setTestingEmail] = useState(false);
  const [emailTestResult, setEmailTestResult] = useState<{ type: 'success' | 'error', msg: string } | null>(null);

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
      lead_email: client.lead_email || '',
      lead_email_password: '',
      email_enabled: client.email_enabled,
    });
    setShowForm(true);
    setEmailTestResult(null);
  };

  const cancelForm = () => {
    setShowForm(false);
    setEditingId(null);
    setForm(emptyForm);
    setError('');
    setEmailTestResult(null);
  };

  const handleTestEmail = async () => {
    if (!editingId) return;
    setTestingEmail(true);
    setEmailTestResult(null);
    try {
      const res = await testClientEmail(editingId);
      setEmailTestResult({ type: 'success', msg: res.message });
    } catch (err: any) {
      setEmailTestResult({ type: 'error', msg: err.message || 'Test failed' });
    } finally {
      setTestingEmail(false);
    }
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

      {success && (
        <div className="card" style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)', marginBottom: 16, padding: '12px 16px', color: '#22c55e' }}>
          ✓ {success}
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
                <Image size={14} style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
                Bot Logo
              </label>
              {editingId && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
                  {form.logo_url && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <img
                        src={form.logo_url}
                        alt="Logo"
                        style={{ width: 40, height: 40, borderRadius: 8, objectFit: 'cover', border: '1px solid var(--color-border)' }}
                      />
                      <button
                        type="button"
                        onClick={async () => {
                          try {
                            await deleteClientLogo(editingId);
                            handleChange('logo_url', '');
                            setSuccess('Logo removed'); setTimeout(() => setSuccess(''), 3000);
                          } catch (e: any) {
                            setError(e.message);
                          }
                        }}
                        style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600 }}
                      >
                        <Trash2 size={14} /> Remove
                      </button>
                    </div>
                  )}
                  <label
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px',
                      background: 'var(--color-bg-secondary)', border: '1px dashed var(--color-border)',
                      borderRadius: 8, cursor: 'pointer', fontSize: '0.85rem', fontWeight: 500,
                      color: 'var(--color-text-muted)', transition: 'all 0.2s',
                    }}
                  >
                    <Upload size={16} />
                    {form.logo_url ? 'Change Logo' : 'Upload Logo'}
                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/svg+xml,image/webp,image/gif"
                      style={{ display: 'none' }}
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        if (file.size > 2 * 1024 * 1024) {
                          setError('File too large. Max 2MB.');
                          return;
                        }
                        try {
                          const res = await uploadClientLogo(editingId, file);
                          handleChange('logo_url', res.logo_url);
                          setSuccess('Logo uploaded!'); setTimeout(() => setSuccess(''), 3000);
                        } catch (err: any) {
                          setError(err.message);
                        }
                        e.target.value = '';
                      }}
                    />
                  </label>
                </div>
              )}
              {!editingId && (
                <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', margin: '4px 0 0' }}>
                  Save the client first, then upload a logo.
                </p>
              )}
            </div>
          </div>

          {/* Email Settings Section */}
          <div style={{ marginTop: 24, borderTop: '1px solid var(--color-border)', paddingTop: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <Mail size={18} style={{ color: '#6366f1' }} />
              <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>Lead Email Notifications</h3>
              <button
                type="button"
                onClick={() => setForm(prev => ({ ...prev, email_enabled: !prev.email_enabled }))}
                style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', background: 'none', border: 'none', color: form.email_enabled ? '#22c55e' : 'var(--color-text-muted)', fontSize: '0.85rem', fontWeight: 500 }}
              >
                {form.email_enabled ? <ToggleRight size={22} /> : <ToggleLeft size={22} />}
                {form.email_enabled ? 'Enabled' : 'Disabled'}
              </button>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: 16 }}>
              When enabled, captured leads will be automatically emailed to the configured Gmail address.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div>
                <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                  <Mail size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Gmail Address
                </label>
                <input className="input" value={form.lead_email || ''} onChange={(e) => handleChange('lead_email', e.target.value)} placeholder="your-email@gmail.com" />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                  <Lock size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Gmail App Password
                </label>
                <input className="input" type="password" value={form.lead_email_password || ''} onChange={(e) => handleChange('lead_email_password', e.target.value)} placeholder={editingId ? '••••••••••••••••' : 'Enter app password'} />
              </div>
            </div>
            {editingId && (
              <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 12 }}>
                <button className="btn" onClick={handleTestEmail} disabled={testingEmail} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Send size={14} /> {testingEmail ? 'Sending...' : 'Send Test Email'}
                </button>
                {emailTestResult && (
                  <span style={{ fontSize: '0.8rem', color: emailTestResult.type === 'success' ? '#22c55e' : '#ef4444' }}>
                    {emailTestResult.msg}
                  </span>
                )}
              </div>
            )}
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
              <div style={{ gridColumn: '1 / -1', marginTop: 4 }}>
                {client.email_enabled ? (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#22c55e', fontSize: '0.75rem' }}>✉️ Lead emails → {client.lead_email}</span>
                ) : (
                  <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>✉️ Lead emails disabled</span>
                )}
              </div>
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
