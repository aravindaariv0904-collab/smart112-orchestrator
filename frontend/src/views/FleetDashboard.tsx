import React, { useState, useEffect } from 'react';
import { 
  Truck, 
  Shield, 
  AlertCircle, 
  CheckCircle, 
  RefreshCw, 
  Navigation, 
  Gauge, 
  Battery, 
  Radio, 
  Play, 
  RotateCcw,
  MapPin,
  Activity,
  Filter
} from 'lucide-react';
import { EmergencyUnit, Incident } from '../types';
import { api } from '../services/api';
import { telemetryMovementManager, UnitMovementState } from '../services/telemetryService';

interface FleetDashboardProps {
  units: EmergencyUnit[];
  incidents: Incident[];
  onRefresh: () => void;
}

export const FleetDashboard: React.FC<FleetDashboardProps> = ({
  units,
  incidents,
  onRefresh
}) => {
  const [filterType, setFilterType] = useState<string>('ALL');
  const [updatingUnitId, setUpdatingUnitId] = useState<string | null>(null);
  const [selectedUnit, setSelectedUnit] = useState<EmergencyUnit | null>(null);
  const [actionMessage, setActionMessage] = useState<{ text: string; isError?: boolean } | null>(null);
  const [movements, setMovements] = useState<Record<string, UnitMovementState>>({});

  // Subscribe to real-time movements
  useEffect(() => {
    const unsub = telemetryMovementManager.subscribe((active) => {
      setMovements(active);
    });
    return unsub;
  }, []);

  const handleStatusChange = async (unitId: string, newStatus: string) => {
    setUpdatingUnitId(unitId);
    setActionMessage(null);
    try {
      await api.updateUnitStatus(
        unitId,
        newStatus,
        'FLEET_SUPERVISOR',
        `Fleet dashboard manual action: updated to ${newStatus}`
      );
      if (newStatus === 'AVAILABLE') {
        telemetryMovementManager.resetMovement(unitId);
      }
      setActionMessage({ text: `Unit status updated to ${newStatus}.` });
      onRefresh();
    } catch (err: any) {
      setActionMessage({ text: err.message || 'Status update failed', isError: true });
    } finally {
      setUpdatingUnitId(null);
    }
  };

  // Trigger simulated emergency dispatch movement for test / demo
  const handleSimulateDispatchMovement = (unit: EmergencyUnit) => {
    // Pick an active incident or use a default emergency target coordinate in Guntur
    const targetIncident = incidents.find(i => i.status !== 'RESOLVED');
    const targetLat = targetIncident ? targetIncident.latitude : 16.3067;
    const targetLng = targetIncident ? targetIncident.longitude : 80.4365;
    const incId = targetIncident ? targetIncident.id : 'SIM-EMERGENCY';
    const incNum = targetIncident ? targetIncident.incident_number : 'INC-DEMO-112';

    telemetryMovementManager.startMovement(
      unit,
      targetLat,
      targetLng,
      incId,
      incNum
    );

    setActionMessage({
      text: `Emergency movement initiated for ${unit.callsign} towards ${incNum} (${targetLat.toFixed(4)}, ${targetLng.toFixed(4)}). Watch vehicle telemetry track on map!`
    });
  };

  const handleResetMovement = (unitId: string) => {
    telemetryMovementManager.resetMovement(unitId);
    setActionMessage({ text: 'Vehicle movement reset to station base.' });
  };

  const filteredUnits = units.filter(u => {
    if (filterType !== 'ALL' && u.unit_type !== filterType) return false;
    return true;
  });

  const availableCount = units.filter(u => u.status === 'AVAILABLE').length;
  const dispatchedCount = units.filter(u => u.status === 'DISPATCHED').length;
  const onSceneCount = units.filter(u => u.status === 'ON_SCENE').length;

  return (
    <div className="h-full p-4 lg:p-6 bg-slate-950 flex flex-col overflow-y-auto">
      {/* KPI Overview Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider block">Total Fleet</span>
            <span className="text-2xl font-black text-white mt-1 block">{units.length}</span>
            <span className="text-[11px] text-slate-500">Ambulances, Fire &amp; Police Patrols</span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300">
            <Truck className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider block">Available on Duty</span>
            <span className="text-2xl font-black text-emerald-400 mt-1 block">{availableCount}</span>
            <span className="text-[11px] text-slate-500">Ready for CAD dispatch</span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-950 border border-emerald-800/60 flex items-center justify-center text-emerald-400">
            <CheckCircle className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider block">Dispatched En Route</span>
            <span className="text-2xl font-black text-amber-400 mt-1 block">{dispatchedCount}</span>
            <span className="text-[11px] text-slate-500">Siren active / GPS moving</span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-amber-950 border border-amber-800/60 flex items-center justify-center text-amber-400">
            <Navigation className="w-6 h-6 animate-pulse" />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider block">On Scene</span>
            <span className="text-2xl font-black text-purple-400 mt-1 block">{onSceneCount}</span>
            <span className="text-[11px] text-slate-500">Active emergency mitigation</span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-purple-950 border border-purple-800/60 flex items-center justify-center text-purple-400">
            <Radio className="w-6 h-6" />
          </div>
        </div>
      </div>

      {actionMessage && (
        <div className={`mb-4 p-3 rounded-xl border text-xs flex items-center justify-between animate-in fade-in ${
          actionMessage.isError ? 'bg-rose-950/80 border-rose-600 text-rose-200' : 'bg-emerald-950/80 border-emerald-600 text-emerald-200'
        }`}>
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4" />
            <span>{actionMessage.text}</span>
          </div>
          <button
            onClick={() => setActionMessage(null)}
            className="text-[11px] underline font-bold"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Content Area */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col flex-1 min-h-0">
        {/* Controls Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4 pb-3 border-b border-slate-800">
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <Truck className="w-4 h-4 text-emerald-400" />
              <span>Fleet Telemetry &amp; Dead-Reckoning Navigation Console</span>
            </h2>
            <p className="text-xs text-slate-400">
              Real-time vehicle GPS coordinates, speed, battery, and simulation controls
            </p>
          </div>

          <div className="flex items-center gap-2">
            {/* Filter Buttons */}
            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs font-semibold">
              {['ALL', 'AMBULANCE', 'FIRE_TRUCK', 'POLICE_PATROL'].map((type) => (
                <button
                  key={type}
                  onClick={() => setFilterType(type)}
                  className={`px-3 py-1 rounded-lg transition ${
                    filterType === type ? 'bg-rose-600 text-white' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {type === 'ALL' ? 'ALL UNITS' : type.replace('_', ' ')}
                </button>
              ))}
            </div>

            <button
              onClick={onRefresh}
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
              title="Refresh Fleet"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Units Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 overflow-y-auto pr-1">
          {filteredUnits.map((unit) => {
            const movement = movements[unit.id];
            const isMoving = movement && movement.isMoving;
            const currentLat = movement ? movement.currentLat : unit.latitude;
            const currentLng = movement ? movement.currentLng : unit.longitude;

            let iconEmoji = '🚑';
            if (unit.unit_type === 'FIRE_TRUCK') iconEmoji = '🚒';
            if (unit.unit_type === 'POLICE_PATROL') iconEmoji = '🚓';

            return (
              <div
                key={unit.id}
                className={`p-4 rounded-xl border transition-all ${
                  isMoving
                    ? 'bg-amber-950/20 border-amber-500/60 shadow-lg shadow-amber-950/20'
                    : unit.status === 'ON_SCENE'
                    ? 'bg-purple-950/20 border-purple-500/60'
                    : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
                }`}
              >
                {/* Unit Header */}
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-lg">
                      {iconEmoji}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-sm text-white">{unit.callsign}</span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 font-mono">
                          {unit.unit_type}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400">{unit.station || 'Central Station'}</p>
                    </div>
                  </div>

                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase ${
                    unit.status === 'AVAILABLE'
                      ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                      : unit.status === 'DISPATCHED' || isMoving
                      ? 'bg-amber-950 text-amber-300 border border-amber-800 animate-pulse'
                      : 'bg-purple-950 text-purple-300 border border-purple-800'
                  }`}>
                    {isMoving ? 'EN ROUTE' : unit.status}
                  </span>
                </div>

                {/* Telemetry Stats */}
                <div className="mt-3 p-2.5 bg-slate-900/80 rounded-lg border border-slate-800/80 grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase block font-semibold">Speed &amp; Heading</span>
                    <span className="font-mono text-white flex items-center gap-1 font-bold">
                      <Gauge className="w-3.5 h-3.5 text-sky-400" />
                      <span>{movement ? `${movement.speedKmh.toFixed(0)} km/h` : '0 km/h (Station)'}</span>
                    </span>
                  </div>

                  <div>
                    <span className="text-[10px] text-slate-500 uppercase block font-semibold">Battery / Fuel</span>
                    <span className="font-mono text-emerald-400 flex items-center gap-1 font-bold">
                      <Battery className="w-3.5 h-3.5 text-emerald-400" />
                      <span>96% Optimal</span>
                    </span>
                  </div>

                  <div className="col-span-2 pt-1 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                    <span className="flex items-center gap-1">
                      <MapPin className="w-3 h-3 text-amber-400" />
                      <span>GPS:</span>
                    </span>
                    <span className="text-amber-300 font-bold">
                      {currentLat.toFixed(4)}, {currentLng.toFixed(4)}
                    </span>
                  </div>

                  {movement && (
                    <div className="col-span-2 text-[10px] text-sky-300 font-mono bg-sky-950/40 p-1.5 rounded border border-sky-800/40">
                      Destination: {movement.incidentNumber} • Dist: {movement.distanceKm.toFixed(2)} km • ETA: {Math.ceil(movement.estimatedSecondsRemaining / 60)}m
                    </div>
                  )}
                </div>

                {/* Interactive Simulation & Dispatch Action Controls */}
                <div className="mt-3 pt-2.5 border-t border-slate-800 flex items-center gap-2">
                  {!isMoving ? (
                    <button
                      type="button"
                      onClick={() => handleSimulateDispatchMovement(unit)}
                      disabled={updatingUnitId === unit.id}
                      className="flex-1 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/40 text-emerald-300 border border-emerald-500/40 text-xs font-bold transition flex items-center justify-center gap-1.5"
                      title="Trigger simulated movement towards an emergency scene"
                    >
                      <Play className="w-3 h-3" />
                      <span>Simulate Dispatch Run</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleResetMovement(unit.id)}
                      className="flex-1 py-1.5 rounded-lg bg-amber-600/20 hover:bg-amber-600/40 text-amber-300 border border-amber-500/40 text-xs font-bold transition flex items-center justify-center gap-1.5"
                      title="Stop movement and return to station"
                    >
                      <RotateCcw className="w-3 h-3" />
                      <span>Reset to Station</span>
                    </button>
                  )}

                  {unit.status !== 'AVAILABLE' && (
                    <button
                      type="button"
                      onClick={() => handleStatusChange(unit.id, 'AVAILABLE')}
                      disabled={updatingUnitId === unit.id}
                      className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-bold transition"
                      title="Set status to AVAILABLE"
                    >
                      Clear
                    </button>
                  )}

                  {unit.status === 'DISPATCHED' && (
                    <button
                      type="button"
                      onClick={() => handleStatusChange(unit.id, 'ON_SCENE')}
                      disabled={updatingUnitId === unit.id}
                      className="px-2.5 py-1.5 rounded-lg bg-purple-600/30 hover:bg-purple-600/50 text-purple-200 border border-purple-500/40 text-xs font-bold transition"
                      title="Mark as arrived on scene"
                    >
                      On Scene
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};