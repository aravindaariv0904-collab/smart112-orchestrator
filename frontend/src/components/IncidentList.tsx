import React, { useState } from 'react';
import { AlertCircle, Clock, ShieldAlert, CheckCircle2, ChevronRight, Search, Filter } from 'lucide-react';
import { Incident } from '../types';

interface IncidentListProps {
  incidents: Incident[];
  selectedIncident: Incident | null;
  onSelectIncident: (incident: Incident) => void;
  isLoading: boolean;
}

export const IncidentList: React.FC<IncidentListProps> = ({
  incidents,
  selectedIncident,
  onSelectIncident,
  isLoading
}) => {
  const [filter, setFilter] = useState<'ALL' | 'CRITICAL' | 'NEEDS_REVIEW' | 'ACTIVE'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const filtered = incidents.filter(inc => {
    // Tab filter
    if (filter === 'CRITICAL' && inc.severity !== 'LEVEL_1_CRITICAL') return false;
    if (filter === 'NEEDS_REVIEW' && !inc.requires_human_review) return false;
    if (filter === 'ACTIVE' && ['RESOLVED', 'CANCELLED'].includes(inc.status)) return false;

    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchNum = inc.incident_number.toLowerCase().includes(q);
      const matchDesc = inc.description.toLowerCase().includes(q);
      const matchCat = inc.category.toLowerCase().includes(q);
      const matchAddr = (inc.address || '').toLowerCase().includes(q);
      if (!matchNum && !matchDesc && !matchCat && !matchAddr) return false;
    }

    return true;
  });

  return (
    <div className="flex flex-col h-full bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
      {/* Search and Filters */}
      <div className="p-3 border-b border-slate-800 space-y-2.5">
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search emergency logs, ID, category..."
            className="w-full bg-slate-950 text-xs text-slate-200 pl-8 pr-3 py-2 rounded-lg border border-slate-800 focus:outline-none focus:border-rose-500 focus:ring-1 focus:ring-rose-500 placeholder-slate-500"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto text-[11px] pb-0.5">
          <button
            onClick={() => setFilter('ALL')}
            className={`px-2.5 py-1 rounded-md font-medium transition ${
              filter === 'ALL'
                ? 'bg-slate-700 text-white'
                : 'bg-slate-800/80 text-slate-400 hover:text-slate-200'
            }`}
          >
            All ({incidents.length})
          </button>
          <button
            onClick={() => setFilter('CRITICAL')}
            className={`px-2.5 py-1 rounded-md font-medium transition flex items-center gap-1 ${
              filter === 'CRITICAL'
                ? 'bg-rose-900/80 text-rose-200 border border-rose-500/50'
                : 'bg-slate-800/80 text-slate-400 hover:text-slate-200'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse"></span>
            Critical ({incidents.filter(i => i.severity === 'LEVEL_1_CRITICAL').length})
          </button>
          <button
            onClick={() => setFilter('NEEDS_REVIEW')}
            className={`px-2.5 py-1 rounded-md font-medium transition flex items-center gap-1 ${
              filter === 'NEEDS_REVIEW'
                ? 'bg-amber-900/80 text-amber-200 border border-amber-500/50'
                : 'bg-slate-800/80 text-slate-400 hover:text-slate-200'
            }`}
          >
            Review ({incidents.filter(i => i.requires_human_review).length})
          </button>
          <button
            onClick={() => setFilter('ACTIVE')}
            className={`px-2.5 py-1 rounded-md font-medium transition ${
              filter === 'ACTIVE'
                ? 'bg-sky-900/80 text-sky-200 border border-sky-500/50'
                : 'bg-slate-800/80 text-slate-400 hover:text-slate-200'
            }`}
          >
            Active
          </button>
        </div>
      </div>

      {/* Incident List Body */}
      <div className="flex-1 overflow-y-auto divide-y divide-slate-800/60 p-1">
        {isLoading && incidents.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400 space-y-2">
            <div className="w-6 h-6 border-2 border-rose-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
            <p>Syncing emergency dispatch feed...</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400 space-y-1">
            <CheckCircle2 className="w-8 h-8 text-emerald-400/60 mx-auto" />
            <p className="font-semibold text-slate-300">No Incidents Found</p>
            <p className="text-[11px] text-slate-500">Matching criteria returned 0 emergencies.</p>
          </div>
        ) : (
          filtered.map(inc => {
            const isSelected = selectedIncident?.id === inc.id;
            const isCritical = inc.severity === 'LEVEL_1_CRITICAL';

            return (
              <div
                key={inc.id}
                role="button"
                tabIndex={0}
                aria-pressed={isSelected}
                onClick={() => onSelectIncident(inc)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    onSelectIncident(inc);
                  }
                }}
                className={`p-3 rounded-lg cursor-pointer transition flex items-start gap-3 select-none ${
                  isSelected
                    ? 'bg-rose-950/40 border border-rose-500/40 shadow-lg'
                    : 'hover:bg-slate-800/60 border border-transparent'
                }`}
              >
                {/* Severity Indicator Bar */}
                <div
                  className={`w-1 self-stretch rounded-full flex-shrink-0 ${
                    isCritical
                      ? 'bg-rose-500 ring-2 ring-rose-500/30'
                      : inc.severity === 'LEVEL_2_HIGH'
                      ? 'bg-orange-500'
                      : 'bg-amber-500'
                  }`}
                />

                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center justify-between gap-1">
                    <span className="font-mono font-bold text-xs text-white tracking-wide">
                      {inc.incident_number}
                    </span>
                    <span
                      className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                        inc.status === 'REPORTED'
                          ? 'bg-sky-950 text-sky-300 border border-sky-800'
                          : inc.status === 'ASSESSED'
                          ? 'bg-purple-950 text-purple-300 border border-purple-800'
                          : inc.status === 'RECOMMENDED'
                          ? 'bg-indigo-950 text-indigo-300 border border-indigo-800'
                          : inc.status === 'DISPATCHED'
                          ? 'bg-amber-950 text-amber-300 border border-amber-800 animate-pulse'
                          : inc.status === 'ON_SCENE'
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {inc.status}
                    </span>
                  </div>

                  <p className="text-xs font-semibold text-slate-200 truncate">
                    {inc.category}
                  </p>

                  <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">
                    {inc.description}
                  </p>

                  {/* Warning Pill if Requires Review */}
                  {inc.requires_human_review && (
                    <div className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-rose-950/60 border border-rose-500/40 text-rose-300 text-[10px] font-semibold">
                      <AlertCircle className="w-3 h-3 text-rose-400 flex-shrink-0" />
                      <span>Review Required</span>
                    </div>
                  )}

                  <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1">
                    <span className="truncate max-w-[150px]">
                      {inc.address || 'Coordinates only'}
                    </span>
                    <span>{inc.created_at ? new Date(inc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Live'}</span>
                  </div>
                </div>

                <ChevronRight className={`w-4 h-4 text-slate-500 self-center flex-shrink-0 ${isSelected ? 'text-rose-400 transform translate-x-0.5' : ''}`} />
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

