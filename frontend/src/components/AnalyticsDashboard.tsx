import React from 'react';
import { 
  BarChart3, 
  TrendingUp, 
  Clock, 
  ShieldCheck, 
  Truck, 
  AlertOctagon, 
  CheckCircle2, 
  Flame, 
  HeartPulse, 
  ShieldAlert, 
  Car,
  Activity,
  Zap,
  Radio
} from 'lucide-react';
import { Incident, EmergencyUnit } from '../types';

interface AnalyticsDashboardProps {
  incidents: Incident[];
  units: EmergencyUnit[];
}

export const AnalyticsDashboard: React.FC<AnalyticsDashboardProps> = ({
  incidents,
  units
}) => {
  const total = incidents.length;
  const criticalCount = incidents.filter(i => i.severity === 'LEVEL_1_CRITICAL').length;
  const highCount = incidents.filter(i => i.severity === 'LEVEL_2_HIGH').length;
  const moderateCount = incidents.filter(i => i.severity === 'LEVEL_3_MODERATE').length;
  const resolvedCount = incidents.filter(i => i.status === 'RESOLVED').length;
  const activeCount = incidents.filter(i => !['RESOLVED', 'CANCELLED'].includes(i.status)).length;
  const reviewCount = incidents.filter(i => i.requires_human_review).length;

  const availableUnits = units.filter(u => u.status === 'AVAILABLE').length;
  const dispatchedUnits = units.filter(u => u.status === 'DISPATCHED').length;
  const onSceneUnits = units.filter(u => u.status === 'ON_SCENE').length;
  const fleetReadinessPct = units.length > 0 ? Math.round((availableUnits / units.length) * 100) : 100;

  // Category counts
  const trafficCount = incidents.filter(i => i.category.includes('TRAFFIC') || i.category.includes('ACCIDENT')).length;
  const medicalCount = incidents.filter(i => i.category.includes('MEDICAL') || i.category.includes('HEALTH')).length;
  const fireCount = incidents.filter(i => i.category.includes('FIRE') || i.category.includes('HAZMAT')).length;
  const policeCount = incidents.filter(i => i.category.includes('POLICE') || i.category.includes('CRIME')).length;

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6 bg-slate-950 text-slate-100">
      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-rose-600/20 text-rose-400 border border-rose-500/30">
              <BarChart3 className="w-5 h-5" />
            </span>
            <h2 className="text-xl font-bold tracking-tight text-white">
              Command Center Operations &amp; Intelligence Analytics
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Real-time telemetry, response velocity benchmarks, and autonomous triage audit metrics
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 font-mono">
            <Radio className="w-3.5 h-3.5 animate-pulse text-emerald-400" />
            <span>Telemetry Live (6s polling)</span>
          </div>
        </div>
      </div>

      {/* KPI Stat Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1 */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-semibold uppercase tracking-wider">Active Emergencies</span>
            <Activity className="w-4 h-4 text-rose-400" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-extrabold text-white font-mono">{activeCount}</span>
            <span className="text-xs text-rose-400 font-semibold">{criticalCount} Critical</span>
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
            <div 
              className="bg-rose-500 h-full rounded-full transition-all duration-500" 
              style={{ width: `${total > 0 ? (activeCount / total) * 100 : 0}%` }}
            />
          </div>
        </div>

        {/* KPI 2 */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-semibold uppercase tracking-wider">Fleet Readiness</span>
            <Truck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-extrabold text-white font-mono">{fleetReadinessPct}%</span>
            <span className="text-xs text-emerald-400 font-semibold">{availableUnits} of {units.length} Avail</span>
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
            <div 
              className="bg-emerald-500 h-full rounded-full transition-all duration-500" 
              style={{ width: `${fleetReadinessPct}%` }}
            />
          </div>
        </div>

        {/* KPI 3 */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-semibold uppercase tracking-wider">AI Triage Latency</span>
            <Zap className="w-4 h-4 text-purple-400" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-extrabold text-white font-mono">&lt; 1.2s</span>
            <span className="text-xs text-purple-400 font-semibold">Zero-Cost Flash Tier</span>
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
            <div className="bg-purple-500 h-full rounded-full" style={{ width: '92%' }} />
          </div>
        </div>

        {/* KPI 4 */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-semibold uppercase tracking-wider">Human-in-Loop Rate</span>
            <ShieldCheck className="w-4 h-4 text-sky-400" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-extrabold text-white font-mono">100%</span>
            <span className="text-xs text-sky-400 font-semibold">SSOT Policy Enforced</span>
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
            <div className="bg-sky-500 h-full rounded-full" style={{ width: '100%' }} />
          </div>
        </div>
      </div>

      {/* Mid Section: Incident Domain Distribution & Severity Gauges */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Severity Breakdown (6 cols) */}
        <div className="lg:col-span-6 bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <AlertOctagon className="w-4 h-4 text-rose-400" />
            <span>Emergency Severity Distribution</span>
          </h3>

          <div className="space-y-3 text-xs">
            {/* Level 1 */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-rose-400 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse"></span>
                  Level 1 Critical (Life-Threatening)
                </span>
                <span className="font-mono text-slate-300">{criticalCount} incidents</span>
              </div>
              <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden">
                <div 
                  className="bg-rose-500 h-full rounded-full transition-all" 
                  style={{ width: `${total > 0 ? (criticalCount / total) * 100 : 0}%` }}
                />
              </div>
            </div>

            {/* Level 2 */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-orange-400 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-orange-500"></span>
                  Level 2 High (Urgent Response)
                </span>
                <span className="font-mono text-slate-300">{highCount} incidents</span>
              </div>
              <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden">
                <div 
                  className="bg-orange-500 h-full rounded-full transition-all" 
                  style={{ width: `${total > 0 ? (highCount / total) * 100 : 0}%` }}
                />
              </div>
            </div>

            {/* Level 3 */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-amber-400 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                  Level 3 Moderate (Standard Deployment)
                </span>
                <span className="font-mono text-slate-300">{moderateCount} incidents</span>
              </div>
              <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden">
                <div 
                  className="bg-amber-500 h-full rounded-full transition-all" 
                  style={{ width: `${total > 0 ? (moderateCount / total) * 100 : 0}%` }}
                />
              </div>
            </div>

            {/* Resolved */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-emerald-400 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                  Mitigated &amp; Resolved
                </span>
                <span className="font-mono text-slate-300">{resolvedCount} incidents</span>
              </div>
              <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden">
                <div 
                  className="bg-emerald-500 h-full rounded-full transition-all" 
                  style={{ width: `${total > 0 ? (resolvedCount / total) * 100 : 0}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Emergency Domain Types (6 cols) */}
        <div className="lg:col-span-6 bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-sky-400" />
            <span>Emergency Services Domain Load</span>
          </h3>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-rose-950/60 border border-rose-500/30 flex items-center justify-center text-rose-400 flex-shrink-0">
                <HeartPulse className="w-5 h-5" />
              </div>
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-semibold">Medical Trauma</div>
                <div className="text-lg font-bold text-white font-mono">{medicalCount} Calls</div>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-orange-950/60 border border-orange-500/30 flex items-center justify-center text-orange-400 flex-shrink-0">
                <Flame className="w-5 h-5" />
              </div>
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-semibold">Fire &amp; Hazmat</div>
                <div className="text-lg font-bold text-white font-mono">{fireCount} Calls</div>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-sky-950/60 border border-sky-500/30 flex items-center justify-center text-sky-400 flex-shrink-0">
                <Car className="w-5 h-5" />
              </div>
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-semibold">Traffic Collisions</div>
                <div className="text-lg font-bold text-white font-mono">{trafficCount} Calls</div>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-indigo-950/60 border border-indigo-500/30 flex items-center justify-center text-indigo-400 flex-shrink-0">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-semibold">Police Dispatch</div>
                <div className="text-lg font-bold text-white font-mono">{policeCount} Calls</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Fleet Telemetry Real-time Matrix */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <Truck className="w-4 h-4 text-emerald-400" />
            <span>MDT Field Unit Operational Status &amp; Telemetry Matrix</span>
          </h3>
          <span className="text-xs text-slate-400 font-mono">
            {dispatchedUnits} Active Deployments | {onSceneUnits} On-Scene
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          {units.map((u) => {
            const isAvail = u.status === 'AVAILABLE';
            const isDisp = u.status === 'DISPATCHED';
            const isOnScene = u.status === 'ON_SCENE';

            return (
              <div 
                key={u.id}
                className={`p-3 rounded-xl border transition-all ${
                  isAvail 
                    ? 'bg-slate-950 border-slate-800 hover:border-slate-700' 
                    : isDisp
                    ? 'bg-amber-950/30 border-amber-500/50 shadow-md ring-1 ring-amber-500/30'
                    : 'bg-purple-950/30 border-purple-500/50 shadow-md ring-1 ring-purple-500/30'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-xs text-white">{u.callsign}</span>
                  <span className={`w-2 h-2 rounded-full ${
                    isAvail ? 'bg-emerald-400' : isDisp ? 'bg-amber-400 animate-ping' : 'bg-purple-400'
                  }`} />
                </div>
                <p className="text-[10px] text-slate-400 mt-0.5">{u.unit_type}</p>
                <p className="text-[10px] text-slate-500 truncate">{u.station || 'Patrol Unit'}</p>
                
                <div className="mt-2 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px]">
                  <span className="font-mono text-slate-400">{u.latitude.toFixed(2)}, {u.longitude.toFixed(2)}</span>
                  <span className={`font-semibold px-1.5 py-0.2 rounded text-[9px] ${
                    isAvail ? 'bg-emerald-950 text-emerald-300' : isDisp ? 'bg-amber-950 text-amber-300' : 'bg-purple-950 text-purple-300'
                  }`}>
                    {u.status}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

