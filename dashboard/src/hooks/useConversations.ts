import { useState, useEffect, useCallback } from 'react';
import { getConversations, getActiveConversations, getConversation, type Conversation, type ConversationDetail } from '../lib/api';

export function useConversations(params: Record<string, string | number> = {}) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getConversations(params);
      setConversations(data);
    } catch (err) {
      console.error('Failed to fetch conversations', err);
    } finally {
      setLoading(false);
    }
  }, [JSON.stringify(params)]);

  useEffect(() => { refresh(); }, [refresh]);

  return { conversations, loading, refresh };
}

export function useActiveConversations(clientId?: string | null) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getActiveConversations(clientId || undefined);
      setConversations(data);
    } catch (err) {
      console.error('Failed to fetch active conversations', err);
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => { refresh(); }, [refresh]);

  return { conversations, loading, refresh };
}

export function useConversationDetail(id: string | null) {
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!id) { setDetail(null); return; }
    setLoading(true);
    try {
      const data = await getConversation(id);
      setDetail(data);
    } catch (err) {
      console.error('Failed to fetch conversation detail', err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { refresh(); }, [refresh]);

  return { detail, loading, refresh };
}
