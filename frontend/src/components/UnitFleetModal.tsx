import React, { useState } from 'react';
import { X, Truck, Shield, AlertCircle, CheckCircle, RefreshCw } from 'lucide-react';
import { EmergencyUnit } from '../types';
import { api } from '../services/api';

interface UnitFleetModalProps {
  isOpen: boolean;
  onClose: () => void;
  units: EmergencyUnit[];
  onRefreshUnits: () => void;
}

export const UnitFleetModal: React.FC<UnitFleetModalProps> = ({
  isOpen,
  onClose,
  units,
  onRefreshUnits
}) => {
  const [filterType, setFilterType] = useState<string>('ALL');
  const [updatingUnitId, setUpdatingUnitId] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleStatusChange = async (unitId: string, newStatus: string) => {
    setUpdatingUnitId(unitId);
    try {
      await api.updateUnitStatus(unitId, newStatus, 'DISPATCHER_SARAH', `Fleet overview manual override to ${newStatus}`);
      onRefreshUnits();
    } catch (err: any) {
      alert(`Status update failed: ${err.message}`);
    } finally {
      setUpdatingUnitId(null);
    }
  };

  const filtered = units.filter(u => {
    if (filterType !== 'ALL' && u.unit_type !== filterType) return false;
    return true;
  });

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-600/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Truck className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Emergency Response Fleet Monitor</h3>
              <p className="text-[11px] text-slate-400">
                10 Units Stationed Across Guntur &amp; Vijayawada Corridor
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Filters */}
        <div className="px-6 py-3 border-b border-slate-800 bg-slate-950 flex items-center gap-2 text-xs">
          <span className="text-slate-400 font-semibold text-[11px] uppercase mr-2">Filter Type:</span>
          {['ALL', 'AMBULANCE', 'FIRE_TRUCK', 'POLICE_PATROL'].map((type) => (
            <button
              key={type}
              onClick={() => setFilterType(type)}
              className={`px-3 py-1 rounded-md text-xs font-semibold transition ${
                filterType === type
                  ? 'bg-rose-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {type}
            </button>
          ))}
        </div>

        {/* List of Units */}
        <div className="p-6 overflow-y-auto space-y-2.5">
          {filtered.map((unit) => {
            const isAvail = unit.status === 'AVAILABLE';
            const isDispatched = unit.status === 'DISPATCHED';
            const isOnScene = unit.status === 'ON_SCENE';

            return (
              <div
                key={unit.id}
                className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-xs text-white tracking-wider">{unit.callsign}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                      {unit.unit_type}
                    </span>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                        isAvail
                          ? 'bg-emerald-950/80 text-emerald-300 border-emerald-500/40'
                          : isDispatched
                          ? 'bg-amber-950/80 text-amber-300 border-amber-500/40 animate-pulse'
                          : 'bg-purple-950/80 text-purple-300 border-purple-500/40'
                      }`}
                    >
                      {unit.status}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">{unit.station || 'Patrol Unit'}</p>
                  <p className="text-[10px] text-slate-500 font-mono">
                    GPS: {unit.latitude.toFixed(4)}, {unit.longitude.toFixed(4)}
                  </p>
                </div>

                {/* Quick Status Toggle */}
                <div className="flex items-center gap-1.5 text-xs">
                  <button
                    disabled={updatingUnitId === unit.id || isAvail}
                    onClick={() => handleStatusChange(unit.id, 'AVAILABLE')}
                    className="px-2.5 py-1 rounded bg-slate-800 hover:bg-emerald-900/60 disabled:opacity-40 text-slate-200 border border-slate-700 text-[11px] font-medium transition"
                  >
                    Available
                  </button>
                  <button
                    disabled={updatingUnitId === unit.id || isOnScene}
                    onClick={() => handleStatusChange(unit.id, 'ON_SCENE')}
                    className="px-2.5 py-1 rounded bg-slate-800 hover:bg-purple-900/60 disabled:opacity-40 text-slate-200 border border-slate-700 text-[11px] font-medium transition"
                  >
                    On Scene
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

