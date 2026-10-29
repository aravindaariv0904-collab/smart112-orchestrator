import React from 'react';
import { 
  Siren, 
  Shield, 
  Database, 
  Sparkles, 
  PlusCircle, 
  Truck, 
  RefreshCw, 
  Trash2,
  Radio,
  BarChart3,
  FileText,
  Activity
} from 'lucide-react';

export type PortalTab = 'CAD' | 'PUBLIC' | 'MDT' | 'ANALYTICS' | 'AUDIT';

interface HeaderProps {
  activeTab: PortalTab;
  setActiveTab: (tab: PortalTab) => void;
  onOpenCallSimulator: () => void;
  onOpenFleetMonitor: () => void;
  onRefresh: () => void;
  onPurgeQueue: () => void;
  isLoading: boolean;
  activeCount: number;
  availableUnitsCount: number;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  onOpenCallSimulator,
  onOpenFleetMonitor,
  onRefresh,
  onPurgeQueue,
  isLoading,
  activeCount,
  availableUnitsCount
}) => {
  return (
    <header className="bg-slate-900 border-b border-slate-800 px-5 py-3 flex flex-wrap items-center justify-between gap-4 shadow-xl select-none sticky top-0 z-50">
      {/* Brand & Identity */}
      <div className="flex items-center gap-3">
        <div 
          onClick={() => setActiveTab('CAD')}
          className="w-10 h-10 rounded-xl bg-gradient-to-tr from-rose-600 to-red-500 flex items-center justify-center shadow-lg shadow-rose-950/40 ring-1 ring-rose-400/30 cursor-pointer hover:scale-105 transition-transform"
        >
          <Siren className="w-5 h-5 text-white animate-pulse" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 
              onClick={() => setActiveTab('CAD')}
              className="text-lg font-black tracking-tight text-white flex items-center gap-2 cursor-pointer"
            >
              SMART 112
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30 font-bold tracking-normal">
                CRITICAL DISPATCH
              </span>
            </h1>
          </div>
          <p className="text-[11px] text-slate-400 flex items-center gap-1.5">
            <span>AI-Augmented Emergency Operations</span>
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-700 font-bold uppercase tracking-wider">
              Simulated data
            </span>
          </p>
        </div>
      </div>

      {/* Primary Multi-Tier View Navigation Tabs */}
      <nav className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800 shadow-inner">
        <button
          onClick={() => setActiveTab('CAD')}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
            activeTab === 'CAD'
              ? 'bg-rose-600 text-white shadow-md shadow-rose-900/40'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          <span>CAD Operations</span>
          {activeCount > 0 && (
            <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-rose-950 border border-rose-400 text-rose-200 font-bold animate-pulse">
              {activeCount}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('PUBLIC')}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
            activeTab === 'PUBLIC'
              ? 'bg-rose-600 text-white shadow-md shadow-rose-900/40'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
        >
          <Radio className="w-3.5 h-3.5 text-sky-400" />
          <span>Citizen Intake</span>
        </button>

        <button
          onClick={() => setActiveTab('MDT')}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
            activeTab === 'MDT'
              ? 'bg-rose-600 text-white shadow-md shadow-rose-900/40'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
          aria-label="Responder Mobile Data Terminal"
        >
          <Truck className="w-3.5 h-3.5 text-amber-400" />
          <span>Responder MDT</span>
        </button>

        <button
          onClick={() => setActiveTab('ANALYTICS')}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
            activeTab === 'ANALYTICS'
              ? 'bg-rose-600 text-white shadow-md shadow-rose-900/40'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
        >
          <BarChart3 className="w-3.5 h-3.5 text-purple-400" />
          <span>Command Analytics</span>
        </button>

        <button
          onClick={() => setActiveTab('AUDIT')}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
            activeTab === 'AUDIT'
              ? 'bg-rose-600 text-white shadow-md shadow-rose-900/40'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
        >
          <FileText className="w-3.5 h-3.5 text-emerald-400" />
          <span>Audit &amp; Fleet</span>
        </button>
      </nav>

      {/* Operational Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition flex items-center gap-1 text-xs"
          title="Refresh Data Telemetry"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-rose-400' : ''}`} />
        </button>

        <button
          onClick={onPurgeQueue}
          className="px-2.5 py-1.5 rounded-lg bg-slate-800/80 hover:bg-rose-950/60 text-slate-400 hover:text-rose-300 border border-slate-700 text-xs font-medium flex items-center gap-1.5 transition"
          title="Delete all incidents from the local demo database (confirmation required)"
        >
          <Trash2 className="w-3.5 h-3.5 text-rose-400" />
          <span>Clear Incidents</span>
        </button>

        <button
          onClick={onOpenFleetMonitor}
          className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-medium text-xs flex items-center gap-2 transition"
        >
          <Truck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Fleet ({availableUnitsCount} Avail)</span>
        </button>

        <button
          onClick={onOpenCallSimulator}
          className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 text-white font-bold text-xs flex items-center gap-1.5 shadow-lg shadow-rose-900/30 transition ring-1 ring-rose-400/40"
        >
          <PlusCircle className="w-3.5 h-3.5" />
          <span>Simulate 112 Call</span>
        </button>
      </div>
    </header>
  );
};
