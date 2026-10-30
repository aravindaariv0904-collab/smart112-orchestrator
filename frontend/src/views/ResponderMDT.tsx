import React, { useEffect, useMemo, useState } from 'react';
import {
  Truck,
  MapPin,
  Clock,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Radio,
  Activity,
  HeartPulse,
  RefreshCw,
  Info,
  Gauge
} from 'lucide-react';
import { EmergencyUnit, Incident } from '../types';
import { api } from '../services/api';

interface ResponderMDTProps {
  units: EmergencyUnit[];
  incidents: Incident[];
  onRefresh: () => void;
}

type Feedback = { kind: 'success' | 'error' | 'info'; text: string };

const ACTIVE_STATUSES = ['DISPATCHED', 'ON_SCENE'];

/** Great-circle distance in km. Used only to show a straight-line figure, never an ETA. */
function haversineKm(
  aLat: number,
  aLon: number,
  bLat: number,
  bLon: number
): number {
  const toRad = (value: number) => (value * Math.PI) / 180;
  const earthRadiusKm = 6371;
  const dLat = toRad(bLat - aLat);
  const dLon = toRad(bLon - aLon);
  const lat1 = toRad(aLat);
  const lat2 = toRad(bLat);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return earthRadiusKm * 2 * Math.asin(Math.min(1, Math.sqrt(h)));
}

export const ResponderMDT: React.FC<ResponderMDTProps> = ({
  units,
  incidents,
  onRefresh
}) => {
  const [selectedUnitId, setSelectedUnitId] = useState<string>('');
  const [sirenOn, setSirenOn] = useState<boolean>(false);
  const [vitalsNotes, setVitalsNotes] = useState<string>('');
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  // Keep the selected unit valid as the fleet refreshes.
  useEffect(() => {
    if (!selectedUnitId || !units.some((unit) => unit.id === selectedUnitId)) {
      setSelectedUnitId(units[0]?.id || '');
    }
  }, [units, selectedUnitId]);

  const selectedUnit = units.find((unit) => unit.id === selectedUnitId) || units[0] || null;

  // Only show the incident that is actually assigned to this unit.
  const activeIncident = useMemo(() => {
    if (!selectedUnit) return null;
    return (
      incidents.find(
        (incident) =>
          incident.assigned_unit_id === selectedUnit.id &&
          ACTIVE_STATUSES.includes(incident.status)
      ) || null
    );
  }, [incidents, selectedUnit]);

  const straightLineKm =
    selectedUnit && activeIncident
      ? haversineKm(
          selectedUnit.latitude,
          selectedUnit.longitude,
          activeIncident.latitude,
          activeIncident.longitude
        )
      : null;

  const handleUpdateStatus = async (status: 'DISPATCHED' | 'ON_SCENE' | 'AVAILABLE') => {
    if (!selectedUnit) return;

    if (status === 'AVAILABLE') {
      const confirmed = window.confirm(
        'Clear this unit and return it to service?\n\nThis also closes the linked incident as RESOLVED and writes an audit entry.'
      );
      if (!confirmed) return;
    }

    setIsUpdating(true);
    setFeedback(null);
    try {
      const result = await api.updateUnitStatus(
        selectedUnit.id,
        status,
        selectedUnit.callsign,
        vitalsNotes.trim() || `MDT status update to ${status}`
      );
      setFeedback({
        kind: 'success',
        text: result?.message || `Status updated to ${status}.`
      });
      onRefresh();
    } catch (err: any) {
      setFeedback({ kind: 'error', text: err.message || 'Status update failed' });
    } finally {
      setIsUpdating(false);
    }
  };

  const canArrive = selectedUnit?.status === 'DISPATCHED';
  const canClear = selectedUnit?.status === 'DISPATCHED' || selectedUnit?.status === 'ON_SCENE';

  return (
    <div className="h-full bg-slate-950 p-4 lg:p-6 overflow-y-auto">
      {/* MDT Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl mb-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-sky-600 flex items-center justify-center shadow-lg shadow-sky-950">
            <Truck className="w-7 h-7 text-white" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-extrabold text-white tracking-tight">RESPONDER MDT</h1>
              <span className="text-xs px-2 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800 font-mono">
                VEHICLE TABLET TERMINAL
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-700 font-bold uppercase tracking-wider">
                Simulated Fleet
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Mobile Data Terminal — status changes are written to the backend audit log
            </p>
          </div>
        </div>

        {/* Vehicle Selector */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-slate-950 px-3 py-1.5 rounded-xl border border-slate-800">
            <label htmlFor="mdt-unit-select" className="text-xs text-slate-400">
              Vehicle:
            </label>
            <select
              id="mdt-unit-select"
              value={selectedUnit?.id || ''}
              onChange={(e) => {
                setSelectedUnitId(e.target.value);
                setFeedback(null);
              }}
              className="bg-transparent text-xs font-bold text-white focus:outline-none cursor-pointer font-mono"
            >
              {units.length === 0 && <option value="">No units available</option>}
              {units.map((unit) => (
                <option key={unit.id} value={unit.id} className="bg-slate-900 text-white">
                  {unit.callsign} ({unit.unit_type} - {unit.status})
                </option>
              ))}
            </select>
          </div>

          <button
            type="button"
            onClick={onRefresh}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
            title="Refresh MDT data"
            aria-label="Refresh MDT data"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {feedback && (
        <div
          role="status"
          className={`mb-4 p-3 rounded-xl border text-xs font-mono flex items-start gap-2 ${
            feedback.kind === 'success'
              ? 'bg-emerald-950/60 border-emerald-800/80 text-emerald-300'
              : feedback.kind === 'error'
              ? 'bg-rose-950/60 border-rose-800/80 text-rose-300'
              : 'bg-sky-950/60 border-sky-800/80 text-sky-300'
          }`}
        >
          {feedback.kind === 'error' ? (
            <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          )}
          <span>{feedback.text}</span>
        </div>
      )}

      {/* Main MDT Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Active Tactical Mission Card (7 cols) */}
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-rose-500" />
                <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
                  Assigned Mission
                </span>
              </div>
              <span
                className={`text-xs px-2.5 py-1 rounded font-bold font-mono uppercase ${
                  selectedUnit?.status === 'AVAILABLE'
                    ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                    : selectedUnit?.status === 'ON_SCENE'
                    ? 'bg-purple-950 text-purple-400 border border-purple-800'
                    : 'bg-amber-950 text-amber-400 border border-amber-800'
                }`}
              >
                STATUS: {selectedUnit?.status || 'UNKNOWN'}
              </span>
            </div>

            {activeIncident ? (
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <span className="text-xs text-slate-400 font-mono">INCIDENT ID</span>
                    <h2 className="text-2xl font-black text-white font-mono">
                      {activeIncident.incident_number}
                    </h2>
                    <span className="text-xs font-bold text-rose-400 bg-rose-950/60 border border-rose-800/60 px-2 py-0.5 rounded uppercase mt-1 inline-block">
                      {activeIncident.severity} • {activeIncident.category}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-xs text-slate-400 font-mono">STRAIGHT-LINE</span>
                    <div className="text-2xl font-black text-sky-400 font-mono">
                      {straightLineKm !== null ? straightLineKm.toFixed(1) : '—'}{' '}
                      <span className="text-xs">KM</span>
                    </div>
                    <span className="text-[10px] text-slate-500">
                      No routing ETA available
                    </span>
                  </div>
                </div>

                {/* Location */}
                <div className="p-3.5 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                  <div className="flex items-center gap-1.5 text-xs text-slate-400">
                    <MapPin className="w-4 h-4 text-rose-500" />
                    <span className="font-semibold text-white">Target Destination:</span>
                  </div>
                  <p className="text-xs font-medium text-slate-200 pl-5">
                    {activeIncident.address || 'Address not provided by caller'}
                  </p>
                  <p className="text-[11px] font-mono text-slate-500 pl-5">
                    Coordinates: {activeIncident.latitude.toFixed(4)}, {activeIncident.longitude.toFixed(4)}
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

                {/* Navigation availability */}
                <div className="p-3.5 bg-sky-950/20 border border-sky-900/40 rounded-xl flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-sky-600/30 border border-sky-500 flex items-center justify-center text-sky-400 flex-shrink-0">
                    <Gauge className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-white">Turn-by-turn navigation not connected</div>
                    <div className="text-[11px] text-slate-400">
                      No routing provider is configured, so no route, ETA, or bearing is shown.
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-12 text-center text-slate-500">
                <CheckCircle2 className="w-12 h-12 mx-auto text-emerald-500/40 mb-2" />
                <p className="text-sm font-semibold text-slate-300">No Mission Assigned</p>
                <p className="text-xs text-slate-500">
                  This unit has no active assignment. Dispatch must be approved in the CAD console.
                </p>
              </div>
            )}
          </div>

          {/* Action Control Buttons */}
          <div className="pt-4 border-t border-slate-800 space-y-2">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => handleUpdateStatus('DISPATCHED')}
                disabled={isUpdating || !canArrive}
                title={canArrive ? 'Re-confirm en-route state' : 'Only a dispatched unit can be acknowledged'}
                className="p-3 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-bold text-xs text-center shadow-lg transition"
              >
                1. Acknowledge / En Route
              </button>

              <button
                type="button"
                onClick={() => handleUpdateStatus('ON_SCENE')}
                disabled={isUpdating || !canArrive}
                title={canArrive ? 'Mark this unit as on scene' : 'Unit must be dispatched before it can arrive'}
                className="p-3 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-bold text-xs text-center shadow-lg transition"
              >
                2. Arrived On Scene
              </button>

              <button
                type="button"
                onClick={() => handleUpdateStatus('AVAILABLE')}
                disabled={isUpdating || !canClear}
                title={canClear ? 'Clear the unit and resolve the linked incident' : 'Unit is already available'}
                className="p-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-bold text-xs text-center shadow-lg transition"
              >
                3. Clear &amp; Return to Service
              </button>
            </div>
            <p className="text-[10px] text-slate-500 flex items-start gap-1.5">
              <Info className="w-3.5 h-3.5 flex-shrink-0 mt-px" />
              Clearing a unit resolves the linked incident and cannot be undone from the MDT.
              Status buttons are enabled only for valid lifecycle transitions.
            </p>
          </div>
        </div>

        {/* Right Column: Vehicle Diagnostics & Vitals Logger (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Real unit data only */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-400" />
              <span>Unit Record</span>
            </h2>

            <dl className="grid grid-cols-2 gap-3 text-xs">
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                <dt className="text-[10px] text-slate-500 uppercase">Callsign</dt>
                <dd className="font-mono font-bold text-white">{selectedUnit?.callsign || '—'}</dd>
              </div>
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                <dt className="text-[10px] text-slate-500 uppercase">Type</dt>
                <dd className="font-mono font-bold text-slate-200">{selectedUnit?.unit_type || '—'}</dd>
              </div>
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                <dt className="text-[10px] text-slate-500 uppercase">Station</dt>
                <dd className="font-semibold text-slate-200 truncate">
                  {selectedUnit?.station || 'Not recorded'}
                </dd>
              </div>
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                <dt className="text-[10px] text-slate-500 uppercase">Last Update</dt>
                <dd className="font-mono text-slate-300">
                  {selectedUnit?.updated_at
                    ? new Date(selectedUnit.updated_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit'
                      })
                    : 'Unknown'}
                </dd>
              </div>
            </dl>

            <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-[11px] font-mono text-slate-400">
              Position: {selectedUnit ? `${selectedUnit.latitude.toFixed(4)}, ${selectedUnit.longitude.toFixed(4)}` : '—'}
            </div>

            <div className="p-3 bg-amber-950/30 border border-amber-800/60 rounded-xl text-[11px] text-amber-200 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-px" />
              <span>
                Live vehicle telemetry (speed, fuel, oxygen, radio channel) is not connected in
                this prototype. No values are shown rather than fabricating them.
              </span>
            </div>

            {/* Siren Switch — local device control only */}
            <div className="flex items-center justify-between p-3 bg-slate-950 rounded-xl border border-slate-800">
              <div className="flex items-center gap-2 text-xs">
                <ShieldAlert className="w-4 h-4 text-slate-400" />
                <div>
                  <span className="font-bold text-white block">Siren Beacon (local UI)</span>
                  <span className="text-[10px] text-slate-500">
                    Cosmetic toggle — not wired to vehicle hardware
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSirenOn((previous) => !previous)}
                aria-pressed={sirenOn}
                className={`px-3 py-1 rounded-lg text-xs font-bold transition ${
                  sirenOn ? 'bg-rose-600 text-white' : 'bg-slate-800 text-slate-400'
                }`}
              >
                {sirenOn ? 'ACTIVE' : 'OFF'}
              </button>
            </div>

            <div className="flex items-center justify-between p-3 bg-slate-950 rounded-xl border border-slate-800 text-xs">
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-slate-400" />
                <span className="font-mono text-slate-400">Radio channel: not connected</span>
              </div>
              <span className="w-2.5 h-2.5 rounded-full bg-slate-600" />
            </div>
          </div>

          {/* Vitals & Field Observation Notes */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
            <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <HeartPulse className="w-4 h-4 text-rose-400" />
              <span>Paramedic / Officer Field Log</span>
            </h2>

            <label htmlFor="mdt-field-log" className="sr-only">
              Field observations
            </label>
            <textarea
              id="mdt-field-log"
              rows={4}
              value={vitalsNotes}
              onChange={(e) => setVitalsNotes(e.target.value)}
              placeholder="Record observations here. The draft is attached to the audit entry on your next status update."
              className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-sky-500 font-mono"
            />

            <p className="text-[10px] text-slate-500 flex items-start gap-1.5">
              <Clock className="w-3.5 h-3.5 flex-shrink-0 mt-px" />
              Local draft only. It is transmitted with the next status change; there is no
              separate field-note endpoint.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
