import React, { useState, useEffect } from 'react';
import { ShieldAlert, Radio, Activity, Eye, FileText, CheckCircle2 } from 'lucide-react';

interface NavbarProps {
  activeTab: 'public' | 'dispatcher' | 'audit';
  setActiveTab: (tab: 'public' | 'dispatcher' | 'audit') => void;
  unresolvedCount?: number;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  unresolvedCount = 0
}) => {
  const [isHealthy, setIsHealthy] = useState<boolean>(true);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch('/api/v1/health');
        setIsHealthy(res.ok);
      } catch {
        setIsHealthy(false);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-16 bg-slate-900 border-b border-slate-800 px-6 flex items-center justify-between shadow-lg sticky top-0 z-50">
      {/* Brand */}
      <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab('dispatcher')}>
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-red-600 to-rose-500 flex items-center justify-center shadow-lg shadow-red-900/30">
          <ShieldAlert className="w-6 h-6 text-white" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-extrabold text-xl tracking-tight text-white">SMART 112</span>
            <span className="text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 rounded-full bg-red-950/80 text-red-400 border border-red-800/60">
              Zero-Cost Core
            </span>
          </div>
          <p className="text-[11px] text-slate-400 font-medium">Autonomous Emergency Intelligence & Dispatch</p>
        </div>
      </div>

      {/* Tabs */}
      <nav className="flex items-center space-x-1 bg-slate-950/60 p-1 rounded-xl border border-slate-800">
        <button
          onClick={() => setActiveTab('public')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === 'public'
              ? 'bg-red-600 text-white shadow-md'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <Radio className="w-4 h-4" />
          <span>Public Intake</span>
        </button>

        <button
          onClick={() => setActiveTab('dispatcher')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === 'dispatcher'
              ? 'bg-red-600 text-white shadow-md'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <Activity className="w-4 h-4" />
          <span>Dispatcher Console</span>
          {unresolvedCount > 0 && (
            <span className="ml-1.5 px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-red-500 text-white animate-pulse">
              {unresolvedCount}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('audit')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === 'audit'
              ? 'bg-red-600 text-white shadow-md'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Units & Audit</span>
        </button>
      </nav>

      {/* Backend & SSOT Indicator */}
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800">
          <span className={`w-2.5 h-2.5 rounded-full ${isHealthy ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
          <span className="text-xs font-medium text-slate-300">
            {isHealthy ? 'Backend SSOT Connected' : 'Backend Offline'}
          </span>
        </div>
      </div>
    </header>
  );
};
