const API_BASE = import.meta.env.VITE_API_URL || '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

/* ─── Client (tenant) ─── */

export interface Client {
  id: string;
  name: string;
  slug: string;
  bot_name: string;
  primary_color: string;
  welcome_msg: string | null;
  logo_url: string | null;
  company_name: string;
  support_email: string;
  support_phone: string;
  business_hours: string;
  website_url: string | null;
  collection_name: string;
  escalation_keywords: Record<string, unknown> | null;
  lead_email: string | null;
  email_enabled: boolean;
  is_active: boolean;
  created_at: string;
}

export interface ClientCreateInput {
  name: string;
  slug: string;
  bot_name?: string;
  primary_color?: string;
  welcome_msg?: string;
  logo_url?: string;
  company_name?: string;
  support_email?: string;
  support_phone?: string;
  business_hours?: string;
  website_url?: string;
  collection_name?: string;
  lead_email?: string;
  lead_email_password?: string;
  email_enabled?: boolean;
}

export const getClients = () => request<Client[]>('/api/dashboard/clients');

export const createClient = (data: ClientCreateInput) =>
  request<Client>('/api/dashboard/clients', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const getClient = (id: string) =>
  request<Client>(`/api/dashboard/clients/${id}`);

export const updateClient = (id: string, data: Partial<ClientCreateInput & { is_active: boolean }>) =>
  request<Client>(`/api/dashboard/clients/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });

export const deleteClient = (id: string) =>
  request<{ status: string }>(`/api/dashboard/clients/${id}`, {
    method: 'DELETE',
  });

/* ─── Conversations ─── */

export interface Conversation {
  id: string;
  session_id: string;
  user_ip: string | null;
  page_url: string | null;
  status: string;
  started_at: string;
  ended_at: string | null;
  message_count: number;
}

export interface Message {
  id: string;
  role: string;
  content: string;
  message_type: string;
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export const getConversations = (params: Record<string, string | number> = {}) => {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== '' && v !== undefined) qs.set(k, String(v));
  });
  return request<Conversation[]>(`/api/dashboard/conversations?${qs}`);
};

export const getActiveConversations = (clientId?: string) => {
  const qs = clientId ? `?client_id=${clientId}` : '';
  return request<Conversation[]>(`/api/dashboard/conversations/active${qs}`);
};

export const getConversation = (id: string) =>
  request<ConversationDetail>(`/api/dashboard/conversations/${id}`);

/* ─── Stats ─── */

export interface Stats {
  total_conversations: number;
  active_conversations: number;
  escalations_today: number;
  avg_messages_per_conversation: number;
  conversations_today: number;
  total_users: number;
}

export const getStats = (clientId?: string) => {
  const qs = clientId ? `?client_id=${clientId}` : '';
  return request<Stats>(`/api/dashboard/stats${qs}`);
};

/* ─── Escalations ─── */

export interface Escalation {
  id: string;
  conversation_id: string;
  trigger_keyword: string;
  status: string;
  assigned_agent: string | null;
  resolved_at: string | null;
  created_at: string;
}

export const getEscalations = (params: Record<string, string | number> = {}) => {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== '' && v !== undefined) qs.set(k, String(v));
  });
  return request<Escalation[]>(`/api/dashboard/escalations?${qs}`);
};

export const resolveEscalation = (id: string) =>
  request<{ status: string }>(`/api/dashboard/escalations/${id}/resolve`, {
    method: 'POST',
  });

/* ─── Settings ─── */

export interface Setting {
  key: string;
  value: Record<string, unknown>;
  updated_at: string;
}

export const getSettings = () => request<Setting[]>('/api/dashboard/settings');

export const updateSetting = (key: string, value: Record<string, unknown>) =>
  request<{ status: string }>('/api/dashboard/settings', {
    method: 'PUT',
    body: JSON.stringify({ key, value }),
  });

/* ─── Users ─── */

export interface ChatUser {
  id: string;
  identifier: string;
  ip_address: string | null;
  city: string | null;
  country: string | null;
  browser: string | null;
  os: string | null;
  device_type: string | null;
  first_seen: string;
  last_seen: string;
  last_page: string | null;
  total_conversations: number;
  total_messages: number;
  tags: Record<string, unknown> | null;
}

export interface ChatUserDetail extends ChatUser {
  conversations: Conversation[];
}

export const getUsers = (params: Record<string, string | number> = {}) => {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== '' && v !== undefined) qs.set(k, String(v));
  });
  return request<ChatUser[]>(`/api/dashboard/users?${qs}`);
};

export const getUser = (id: string) =>
  request<ChatUserDetail>(`/api/dashboard/users/${id}`);

export const updateUserTags = (id: string, tags: Record<string, unknown>) =>
  request<{ status: string }>(`/api/dashboard/users/${id}/tags`, {
    method: 'PUT',
    body: JSON.stringify({ tags }),
  });

/* ─── Leads ─── */

export interface Lead {
  id: string;
  client_id: string;
  conversation_id: string | null;
  name: string | null;
  email: string | null;
  phone: string | null;
  company: string | null;
  email_sent: boolean;
  email_error: string | null;
  created_at: string;
}

export const getLeads = (params: Record<string, string | number | boolean> = {}) => {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== '' && v !== undefined) qs.set(k, String(v));
  });
  return request<Lead[]>(`/api/dashboard/leads?${qs}`);
};

export const testClientEmail = (clientId: string) =>
  request<{ status: string; message: string }>(`/api/dashboard/clients/${clientId}/test-email`, {
    method: 'POST',
  });

/* ─── Logo Upload ─── */

export const uploadClientLogo = async (clientId: string, file: File): Promise<{ logo_url: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/api/dashboard/clients/${clientId}/logo`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Upload failed');
  }
  return res.json();
};

export const deleteClientLogo = (clientId: string) =>
  request<{ status: string }>(`/api/dashboard/clients/${clientId}/logo`, {
    method: 'DELETE',
  });
