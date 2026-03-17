import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Client, getClients } from '../lib/api';

interface ClientContextType {
  clients: Client[];
  activeClient: Client | null;
  setActiveClientId: (id: string) => void;
  refreshClients: () => Promise<void>;
  loading: boolean;
}

const ClientContext = createContext<ClientContextType>({
  clients: [],
  activeClient: null,
  setActiveClientId: () => {},
  refreshClients: async () => {},
  loading: true,
});

export function ClientProvider({ children }: { children: ReactNode }) {
  const [clients, setClients] = useState<Client[]>([]);
  const [activeClientId, setActiveClientId] = useState<string>(
    localStorage.getItem('active_client_id') || ''
  );
  const [loading, setLoading] = useState(true);

  const refreshClients = async () => {
    try {
      const data = await getClients();
      setClients(data);
      // Auto-select first client if none selected
      if (!activeClientId && data.length > 0) {
        setActiveClientId(data[0].id);
        localStorage.setItem('active_client_id', data[0].id);
      }
    } catch (err) {
      console.error('Failed to load clients:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshClients();
  }, []);

  const handleSetActiveClientId = (id: string) => {
    setActiveClientId(id);
    localStorage.setItem('active_client_id', id);
  };

  const activeClient = clients.find((c) => c.id === activeClientId) || clients[0] || null;

  return (
    <ClientContext.Provider
      value={{
        clients,
        activeClient,
        setActiveClientId: handleSetActiveClientId,
        refreshClients,
        loading,
      }}
    >
      {children}
    </ClientContext.Provider>
  );
}

export function useClient() {
  return useContext(ClientContext);
}
