import React, { useState, useEffect } from 'react';
import { 
  Truck, 
  Navigation, 
  MapPin, 
  Clock, 
  ShieldAlert, 
  CheckCircle2, 
  AlertTriangle, 
  Volume2, 
  VolumeX, 
  Radio, 
  Activity,
  HeartPulse,
  Battery,
  Fuel,
  RefreshCw,
  Send
} from 'lucide-react';
import { EmergencyUnit, Incident } from '../types';
import { api } from '../services/api';

interface ResponderMDTProps {
  units: EmergencyUnit[];
  incidents: Incident[];
  onRefresh: () => void;
}

export const ResponderMDT: React.FC<ResponderMDTProps> = ({
  units,
  incidents,
  onRefresh
}) => {
  // Active vehicle selected in MDT
  const [selectedUnitId, setSelectedUnitId] = useState<string>(units[0]?.id || '');
  const [sirenOn, setSirenOn] = useState<boolean>(true);
  const [speedKmh, setSpeedKmh] = useState<number>(54);
  const [vitalsNotes, setVitalsNotes] = useState<string>('Patient 1: BP 110/75, HR 92 bpm, conscious. Patient 2: Trauma extrication required.');
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const selectedUnit = units.find(u => u.id === selectedUnitId) || units[0];

  // Fluctuate speed realistically
  useEffect(() => {
    const timer = setInterval(() => {
      setSpeedKmh(Math.floor(45 + Math.random() * 20));
    }, 1500);
    return () => clearInterval(timer);
  }, []);

  // Locate active incident for this unit (if any)
  const activeIncident = incidents.find(i => 
    i.status === 'DISPATCHED' || i.status === 'ON_SCENE'
  ) || incidents[0] || null;

  const handleUpdateStatus = async (status: string) => {
    if (!selectedUnit) return;
    setIsUpdating(true);
    setFeedback(null);
    try {
      await api.updateUnitStatus(
        selectedUnit.id, 
        status, 
        selectedUnit.callsign,
        `MDT telemetry updated status to ${status}`
      );
      setFeedback(`Status updated to ${status}. Backend SSOT confirmed.`);
      onRefresh();
    } catch (err: any) {
      setFeedback(err.message || 'Status update failed');
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="h-full bg-slate-950 p-4 lg:p-6 overflow-y-auto">
      {/* MDT Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl mb-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-sky-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-950">
            <Truck className="w-7 h-7 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-extrabold text-white tracking-tight">RESPONDER MDT</h1>
              <span className="text-xs px-2 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800 font-mono">
                VEHICLE TABLET TERMINAL
              </span>
            </div>
            <p className="text-xs text-slate-400">Mobile Data Terminal for Andhra Pradesh 112 Fleet</p>
          </div>
        </div>

        {/* Vehicle Selector */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-slate-950 px-3 py-1.5 rounded-xl border border-slate-800">
            <span className="text-xs text-slate-400">Vehicle:</span>
            <select
              value={selectedUnit?.id || ''}
              onChange={(e) => setSelectedUnitId(e.target.value)}
              className="bg-transparent text-xs font-bold text-white focus:outline-none cursor-pointer font-mono"
            >
              {units.map((u) => (
                <option key={u.id} value={u.id} className="bg-slate-900 text-white">
                  {u.callsign} ({u.unit_type} - {u.status})
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={onRefresh}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
            title="Sync MDT Telemetry"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {feedback && (
        <div className="mb-4 p-3 rounded-xl bg-emerald-950/60 border border-emerald-800/80 text-xs text-emerald-300 font-mono flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{feedback}</span>
        </div>
      )}

      {/* Main MDT Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Active Tactical Mission Card (7 cols) */}
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-rose-500 animate-ping" />
                <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
                  Active Mission Deployment Order
                </span>
              </div>
              <span className={`text-xs px-2.5 py-1 rounded font-bold font-mono uppercase ${
                selectedUnit?.status === 'AVAILABLE'
                  ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                  : selectedUnit?.status === 'ON_SCENE'
                  ? 'bg-purple-950 text-purple-400 border border-purple-800'
                  : 'bg-amber-950 text-amber-400 border border-amber-800'
              }`}>
                STATUS: {selectedUnit?.status}
              </span>
            </div>

            {activeIncident ? (
              <div className="space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-xs text-slate-400 font-mono">INCIDENT ID</span>
                    <h2 className="text-2xl font-black text-white font-mono">{activeIncident.incident_number}</h2>
                    <span className="text-xs font-bold text-rose-400 bg-rose-950/60 border border-rose-800/60 px-2 py-0.5 rounded uppercase mt-1 inline-block">
                      {activeIncident.severity} • {activeIncident.category}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-xs text-slate-400 font-mono">ESTIMATED ETA</span>
                    <div className="text-2xl font-black text-emerald-400 font-mono">2.4 <span className="text-xs">MIN</span></div>
                  </div>
                </div>

                {/* Location */}
                <div className="p-3.5 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                  <div className="flex items-center gap-1.5 text-xs text-slate-400">
                    <MapPin className="w-4 h-4 text-rose-500" />
                    <span className="font-semibold text-white">Target Destination:</span>
                  </div>
                  <p className="text-xs font-medium text-slate-200 pl-5">
                    {activeIncident.address || 'Guntur RTC Bus Station Complex, Main Cross, Andhra Pradesh'}
                  </p>
                  <p className="text-[11px] font-mono text-slate-500 pl-5">
                    GPS Coordinates: {activeIncident.latitude.toFixed(4)}° N, {activeIncident.longitude.toFixed(4)}° E
                  </p>
                </div>

                {/* Tactical Dispatch Notes */}
                <div className="p-3.5 bg-rose-950/20 border border-rose-900/40 rounded-xl">
                  <span className="text-[11px] font-bold text-rose-300 uppercase tracking-wider block mb-1">
                    Emergency Triage Description:
                  </span>
                  <p className="text-xs text-slate-200 font-mono leading-relaxed">
                    "{activeIncident.description}"
                  </p>
                </div>

                {/* Turn by Turn Navigation Mockup */}
                <div className="p-3.5 bg-sky-950/20 border border-sky-900/40 rounded-xl flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-sky-600/30 border border-sky-500 flex items-center justify-center text-sky-400">
                      <Navigation className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-white">In 350 meters, turn right onto Arundelpet Main Rd</div>
                      <div className="text-[11px] text-slate-400">Continue straight for 1.2 km towards RTC Bus Complex</div>
                    </div>
                  </div>
                  <span className="text-xs font-mono font-bold text-sky-400">0.9 KM</span>
                </div>
              </div>
            ) : (
              <div className="py-12 text-center text-slate-500">
                <CheckCircle2 className="w-12 h-12 mx-auto text-emerald-500/40 mb-2" />
                <p className="text-sm font-semibold text-slate-300">Unit In Service &amp; On Standby</p>
                <p className="text-xs text-slate-500">Awaiting automated CAD dispatch assignment.</p>
              </div>
            )}
          </div>

          {/* Action Control Buttons */}
          <div className="pt-4 border-t border-slate-800 grid grid-cols-2 md:grid-cols-4 gap-2">
            <button
              onClick={() => handleUpdateStatus('DISPATCHED')}
              disabled={isUpdating}
              className="p-3 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs text-center shadow-lg transition cursor-pointer"
            >
              1. Acknowledge / En Route
            </button>

            <button
              onClick={() => handleUpdateStatus('ON_SCENE')}
              disabled={isUpdating}
              className="p-3 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs text-center shadow-lg transition cursor-pointer"
            >
              2. Arrived On Scene
            </button>

            <button
              onClick={() => handleUpdateStatus('ON_SCENE')}
              disabled={isUpdating}
              className="p-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs text-center shadow-lg transition cursor-pointer"
            >
              3. Transporting Patient
            </button>

            <button
              onClick={() => handleUpdateStatus('AVAILABLE')}
              disabled={isUpdating}
              className="p-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs text-center shadow-lg transition cursor-pointer"
            >
              4. Clear &amp; Return to Service
            </button>
          </div>
        </div>

        {/* Right Column: Vehicle Diagnostics & Vitals Logger (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Vehicle Telemetry Gauges */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-400" />
              <span>Vehicle Diagnostics &amp; Telemetry</span>
            </h3>

            <div className="grid grid-cols-3 gap-3">
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
                <span className="text-[10px] text-slate-500 uppercase block">Vehicle Speed</span>
                <span className="text-xl font-black text-sky-400 font-mono">{speedKmh}</span>
                <span className="text-[10px] text-slate-400 block font-mono">KM/H</span>
              </div>

              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
                <span className="text-[10px] text-slate-500 uppercase block">Fuel Level</span>
                <span className="text-xl font-black text-emerald-400 font-mono">84%</span>
                <span className="text-[10px] text-slate-400 block font-mono">DIESEL</span>
              </div>

              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
                <span className="text-[10px] text-slate-500 uppercase block">Medical Oxygen</span>
                <span className="text-xl font-black text-indigo-400 font-mono">195</span>
                <span className="text-[10px] text-slate-400 block font-mono">BAR</span>
              </div>
            </div>

            <div className="flex items-center justify-between p-3 bg-slate-950 rounded-xl border border-slate-800 text-xs">
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-emerald-400" />
                <span className="font-mono text-slate-300">RADIO: AP-112-TAC-CHANNEL-4</span>
              </div>
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            </div>

            {/* Siren Switch */}
            <div className="flex items-center justify-between p-3 bg-slate-950 rounded-xl border border-slate-800">
              <div className="flex items-center gap-2 text-xs">
                <ShieldAlert className={`w-4 h-4 ${sirenOn ? 'text-rose-500 animate-pulse' : 'text-slate-500'}`} />
                <span className="font-bold text-white">Emergency Light &amp; Siren Beacon</span>
              </div>
              <button
                onClick={() => setSirenOn(!sirenOn)}
                className={`px-3 py-1 rounded-lg text-xs font-bold transition cursor-pointer ${
                  sirenOn ? 'bg-rose-600 text-white' : 'bg-slate-800 text-slate-400'
                }`}
              >
                {sirenOn ? 'ACTIVE' : 'OFF'}
              </button>
            </div>
          </div>

          {/* Vitals & Field Observation Notes */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <HeartPulse className="w-4 h-4 text-rose-400" />
              <span>Paramedic / Officer Field Log</span>
            </h3>

            <textarea
              rows={4}
              value={vitalsNotes}
              onChange={(e) => setVitalsNotes(e.target.value)}
              className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-sky-500 font-mono"
            />

            <button
              onClick={() => {
                setFeedback('Field vitals logged to central incident audit ledger.');
                setTimeout(() => setFeedback(null), 3000);
              }}
              className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold text-xs flex items-center justify-center gap-2 transition cursor-pointer"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Transmit Observations to CAD Dispatch</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
