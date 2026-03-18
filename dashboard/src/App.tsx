import { useState, useEffect, PropsWithChildren } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import DashboardLayout from './components/layout/DashboardLayout';
import DashboardPage from './pages/DashboardPage';
import ConversationsPage from './pages/ConversationsPage';
import LiveChatPage from './pages/LiveChatPage';
import EscalationsPage from './pages/EscalationsPage';
import UsersPage from './pages/UsersPage';
import SettingsPage from './pages/SettingsPage';
import ClientsPage from './pages/ClientsPage';
import LeadsPage from './pages/LeadsPage';
import LoginPage from './pages/LoginPage';
import { ClientProvider } from './contexts/ClientContext';

function ProtectedRoutes({ children, onLogout }: PropsWithChildren<{ onLogout: () => void }>) {
  return <>{children}</>;
}

function AppRoutes({ onLogout }: { onLogout: () => void }) {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<DashboardLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/conversations" element={<ConversationsPage />} />
          <Route path="/conversations/:id" element={<ConversationsPage />} />
          <Route path="/live" element={<LiveChatPage />} />
          <Route path="/escalations" element={<EscalationsPage />} />
          <Route path="/users" element={<UsersPage />} />
          <Route path="/clients" element={<ClientsPage />} />
          <Route path="/leads" element={<LeadsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    setIsAuthenticated(!!token);
  }, []);

  const handleLogin = () => {
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    setIsAuthenticated(false);
  };

  if (isAuthenticated === null) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
        <div className="spinner" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <ClientProvider>
      <ProtectedRoutes onLogout={handleLogout}>
        <AppRoutes onLogout={handleLogout} />
      </ProtectedRoutes>
    </ClientProvider>
  );
}
