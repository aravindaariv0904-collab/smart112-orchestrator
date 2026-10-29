import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { PublicPortal } from './views/PublicPortal';
import { DispatcherDashboard } from './views/DispatcherDashboard';
import { AuditView } from './views/AuditView';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'public' | 'dispatcher' | 'audit'>('dispatcher');
  const [unresolvedCount, setUnresolvedCount] = useState<number>(0);

  useEffect(() => {
    const fetchCount = async () => {
      try {
        const res = await fetch('/api/v1/incidents');
        if (res.ok) {
          const list = await res.json();
          const active = list.filter((i: any) => i.status !== 'RESOLVED' && i.status !== 'CANCELLED');
          setUnresolvedCount(active.length);
        }
      } catch (err) {
        // Polling error silently handled
      }
    };
    fetchCount();
    const interval = setInterval(fetchCount, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans select-none">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        unresolvedCount={unresolvedCount}
      />
      <main className="flex-1 overflow-hidden">
        {activeTab === 'public' && <PublicPortal />}
        {activeTab === 'dispatcher' && <DispatcherDashboard />}
        {activeTab === 'audit' && <AuditView />}
      </main>
    </div>
  );
};

export default App;
