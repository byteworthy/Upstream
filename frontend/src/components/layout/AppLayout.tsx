import { useState, useEffect } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { authApi } from '@/lib/api';
import { clearTokens, getUser, setUser, isAuthenticated } from '@/lib/auth';
import type { User } from '@/types/api';

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [user, setUserState] = useState<User | null>(getUser());
  const navigate = useNavigate();

  useEffect(() => {
    // Check if user is authenticated
    if (!isAuthenticated()) {
      navigate('/login');
      return;
    }

    // Fetch current user if not cached
    if (!user) {
      authApi
        .getCurrentUser()
        .then((userData) => {
          setUser(userData);
          setUserState(userData);
        })
        .catch(() => {
          // If fetch fails, redirect to login
          clearTokens();
          navigate('/login');
        });
    }
  }, [user, navigate]);

  const handleLogout = async () => {
    await authApi.logout();
    navigate('/login');
  };

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        customerName={user?.customer?.name}
      />
      <div className="flex flex-1 flex-col lg:ml-0">
        <Header user={user} onMenuClick={() => setSidebarOpen(true)} onLogout={handleLogout} />
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
