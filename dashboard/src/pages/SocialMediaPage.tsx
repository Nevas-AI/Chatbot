import { useState, useEffect } from 'react';
import { getSocialPosts, createSocialPost, updateSocialPost, deleteSocialPost, SocialPost, SocialPostCreateInput } from '../lib/api';
import { useClient } from '../contexts/ClientContext';
import { Share2, Plus, ExternalLink, Linkedin, Facebook, Instagram, Twitter, Globe, Calendar, CheckCircle, XCircle, Pencil, Trash2, X } from 'lucide-react';

const PLATFORMS = ['linkedin', 'facebook', 'instagram', 'twitter', 'other'] as const;

const platformMeta: Record<string, { icon: typeof Linkedin; label: string; color: string }> = {
    linkedin: { icon: Linkedin, label: 'LinkedIn', color: '#0A66C2' },
    facebook: { icon: Facebook, label: 'Facebook', color: '#1877F2' },
    instagram: { icon: Instagram, label: 'Instagram', color: '#E4405F' },
    twitter: { icon: Twitter, label: 'Twitter / X', color: '#1DA1F2' },
    other: { icon: Globe, label: 'Other', color: '#65bc47' },
};

const emptyForm: Omit<SocialPostCreateInput, 'client_id'> = {
    platform: 'linkedin',
    post_url: '',
    content: '',
    caption: '',
    is_active: true,
};

export default function SocialMediaPage() {
    const { activeClient } = useClient();
    const [posts, setPosts] = useState<SocialPost[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState<string>('all');
    const [showModal, setShowModal] = useState(false);
    const [editingPost, setEditingPost] = useState<SocialPost | null>(null);
    const [form, setForm] = useState(emptyForm);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        loadPosts();
    }, [activeClient?.id, filter]);

    const loadPosts = async () => {
        setLoading(true);
        try {
            const params: Record<string, string> = {};
            if (activeClient?.id) params.client_id = activeClient.id;
            if (filter !== 'all') params.platform = filter;
            const data = await getSocialPosts(params);
            setPosts(data);
        } catch (err) {
            console.error('Failed to load social posts:', err);
        } finally {
            setLoading(false);
        }
    };

    const openAddModal = () => {
        setEditingPost(null);
        setForm(emptyForm);
        setError('');
        setShowModal(true);
    };

    const openEditModal = (post: SocialPost) => {
        setEditingPost(post);
        setForm({
            platform: post.platform,
            post_url: post.post_url,
            content: post.content,
            caption: post.caption || '',
            is_active: post.is_active,
        });
        setError('');
        setShowModal(true);
    };

    const handleSave = async () => {
        if (!form.post_url.trim()) { setError('Post URL is required'); return; }
        if (!form.content.trim()) { setError('Content is required'); return; }
        if (!activeClient?.id) { setError('No active client selected'); return; }

        setSaving(true);
        setError('');
        try {
            if (editingPost) {
                await updateSocialPost(editingPost.id, form);
            } else {
                await createSocialPost({ ...form, client_id: activeClient.id });
            }
            setShowModal(false);
            loadPosts();
        } catch (err: any) {
            setError(err.message || 'Failed to save');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this social post? This cannot be undone.')) return;
        try {
            await deleteSocialPost(id);
            loadPosts();
        } catch (err) {
            console.error('Failed to delete:', err);
        }
    };

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString('en-IN', {
            day: 'numeric', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    };

    const handleChange = (field: string, value: string | boolean) => {
        setForm(prev => ({ ...prev, [field]: value }));
    };

    return (
        <div>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                <div>
                    <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
                        <Share2 size={24} style={{ color: '#65bc47' }} /> Social Media Content
                    </h1>
                    <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', margin: '4px 0 0 0' }}>
                        Manage social media posts to train your chatbot with the latest offers and promotions.
                    </p>
                </div>
                <button className="btn btn-primary" onClick={openAddModal} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Plus size={16} /> Add Post
                </button>
            </div>

            {/* Platform Filter */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
                {['all', ...PLATFORMS].map(p => {
                    const meta = p === 'all' ? null : platformMeta[p];
                    return (
                        <button
                            key={p}
                            className="btn"
                            onClick={() => setFilter(p)}
                            style={{
                                background: filter === p ? '#65bc47' : 'var(--color-bg-secondary)',
                                color: filter === p ? '#fff' : 'var(--color-text-secondary)',
                                border: filter === p ? '1px solid #65bc47' : '1px solid var(--color-border)',
                                fontSize: '0.8rem',
                                padding: '6px 14px',
                                borderRadius: 8,
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 5,
                            }}
                        >
                            {meta && <meta.icon size={14} />}
                            {p === 'all' ? 'All' : meta?.label}
                        </button>
                    );
                })}
            </div>

            {/* Content */}
            {loading ? (
                <div style={{ textAlign: 'center', padding: 60, color: 'var(--color-text-muted)' }}>Loading posts...</div>
            ) : posts.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 60 }}>
                    <Share2 size={48} style={{ color: 'var(--color-text-muted)', marginBottom: 12 }} />
                    <p style={{ color: 'var(--color-text-muted)', fontSize: '1rem' }}>
                        No social media posts yet. Add your first post to start training your chatbot.
                    </p>
                </div>
            ) : (
                <div style={{ display: 'grid', gap: 16 }}>
                    {posts.map(post => {
                        const meta = platformMeta[post.platform] || platformMeta.other;
                        const Icon = meta.icon;
                        return (
                            <div
                                key={post.id}
                                className="glass-card"
                                style={{ padding: 20, display: 'flex', gap: 16, alignItems: 'flex-start' }}
                            >
                                {/* Platform icon */}
                                <div style={{
                                    width: 44, height: 44, borderRadius: 12,
                                    background: `${meta.color}15`,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    flexShrink: 0,
                                }}>
                                    <Icon size={22} style={{ color: meta.color }} />
                                </div>

                                {/* Content */}
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                                        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: meta.color, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                            {meta.label}
                                        </span>
                                        {post.caption && (
                                            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                                                — {post.caption}
                                            </span>
                                        )}
                                    </div>
                                    <p style={{
                                        fontSize: '0.875rem', color: 'var(--color-text-secondary)',
                                        lineHeight: 1.6, margin: '0 0 10px 0',
                                        display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
                                        overflow: 'hidden',
                                    }}>
                                        {post.content}
                                    </p>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                                        <a
                                            href={post.post_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            style={{ fontSize: '0.8rem', color: '#65bc47', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}
                                        >
                                            <ExternalLink size={13} /> View Post
                                        </a>
                                        <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                                            <Calendar size={12} /> {formatDate(post.created_at)}
                                        </span>
                                        <span style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 4, color: post.ingested ? '#22c55e' : '#f59e0b' }}>
                                            {post.ingested ? <><CheckCircle size={13} /> Ingested</> : <><XCircle size={13} /> Not ingested</>}
                                        </span>
                                        {!post.is_active && (
                                            <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: 999, background: 'rgba(239,68,68,0.1)', color: '#ef4444', fontWeight: 600 }}>
                                                Inactive
                                            </span>
                                        )}
                                    </div>
                                </div>

                                {/* Actions */}
                                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                                    <button className="btn btn-ghost" onClick={() => openEditModal(post)} style={{ padding: 6 }} title="Edit">
                                        <Pencil size={15} />
                                    </button>
                                    <button className="btn btn-danger" onClick={() => handleDelete(post.id)} style={{ padding: 6 }} title="Delete">
                                        <Trash2 size={15} />
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Add/Edit Modal */}
            {showModal && (
                <div
                    style={{
                        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
                    }}
                    onClick={() => setShowModal(false)}
                >
                    <div
                        onClick={e => e.stopPropagation()}
                        style={{
                            background: 'var(--color-bg-secondary)',
                            border: '1px solid var(--color-border)',
                            borderRadius: 16, padding: 28, width: '100%', maxWidth: 560,
                            boxShadow: '0 12px 40px rgba(0,0,0,0.15)',
                            maxHeight: '90vh', overflowY: 'auto',
                        }}
                    >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, margin: 0 }}>
                                {editingPost ? 'Edit Post' : 'Add Social Media Post'}
                            </h2>
                            <button onClick={() => setShowModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}>
                                <X size={20} />
                            </button>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                            {/* Platform */}
                            <div>
                                <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>Platform</label>
                                <select
                                    className="input"
                                    value={form.platform}
                                    onChange={e => handleChange('platform', e.target.value)}
                                >
                                    {PLATFORMS.map(p => (
                                        <option key={p} value={p}>{platformMeta[p].label}</option>
                                    ))}
                                </select>
                            </div>

                            {/* Post URL */}
                            <div>
                                <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                                    Post URL <span style={{ color: '#ef4444' }}>*</span>
                                </label>
                                <input
                                    className="input"
                                    value={form.post_url}
                                    onChange={e => handleChange('post_url', e.target.value)}
                                    placeholder="https://www.linkedin.com/posts/..."
                                />
                            </div>

                            {/* Caption */}
                            <div>
                                <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>Caption (optional label)</label>
                                <input
                                    className="input"
                                    value={form.caption || ''}
                                    onChange={e => handleChange('caption', e.target.value)}
                                    placeholder="E.g. Summer Sale 2025"
                                />
                            </div>

                            {/* Content */}
                            <div>
                                <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                                    Post Content <span style={{ color: '#ef4444' }}>*</span>
                                </label>
                                <textarea
                                    className="input"
                                    value={form.content}
                                    onChange={e => handleChange('content', e.target.value)}
                                    placeholder="Paste the full post content here. This will be used to train the chatbot..."
                                    rows={6}
                                    style={{ resize: 'vertical', fontFamily: 'inherit' }}
                                />
                            </div>

                            {/* Active toggle */}
                            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: '0.85rem' }}>
                                <input
                                    type="checkbox"
                                    checked={form.is_active}
                                    onChange={e => handleChange('is_active', e.target.checked)}
                                    style={{ accentColor: '#65bc47', width: 16, height: 16 }}
                                />
                                Active — include in chatbot training
                            </label>

                            {error && (
                                <div style={{ color: '#ef4444', fontSize: '0.85rem', padding: '8px 12px', background: 'rgba(239,68,68,0.08)', borderRadius: 8 }}>
                                    {error}
                                </div>
                            )}

                            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 4 }}>
                                <button className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
                                <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                                    {saving ? 'Saving...' : editingPost ? 'Update Post' : 'Add & Train Chatbot'}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
