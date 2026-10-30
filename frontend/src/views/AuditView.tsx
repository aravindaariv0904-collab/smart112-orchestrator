import React, { useState, useEffect } from 'react';
import { Shield, Clock, User, CheckCircle, Navigation, RefreshCw, FileText, Activity } from 'lucide-react';
import { MapUnit } from '../map/LeafletMap';

interface AuditRecord {
  id: string;
  incident_id: string;
  actor: string;
  action: string;
  details: string;
  timestamp: string;
}

export const AuditView: React.FC = () => {
  const [units, setUnits] = useState<MapUnit[]>([]);
  const [incidents, setIncidents] = useState<any[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>('');
  const [auditLogs, setAuditLogs] = useState<AuditRecord[]>([]);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const fetchData = async () => {
    try {
      const [uRes, iRes] = await Promise.all([
        fetch('/api/v1/units'),
        fetch('/api/v1/incidents')
      ]);
      if (uRes.ok) setUnits(await uRes.json());
      if (iRes.ok) {
        const incData = await iRes.json();
        setIncidents(incData);
        if (!selectedIncidentId && incData.length > 0) {
          setSelectedIncidentId(incData[0].id);
        }
      }
    } catch (e) {
      console.error('Failed to load audit/unit data', e);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (!selectedIncidentId) return;
    const fetchAudit = async () => {
      try {
        const res = await fetch(`/api/v1/audit/${selectedIncidentId}`);
        if (res.ok) {
          setAuditLogs(await res.json());
        }
      } catch (e) {
        console.error('Failed to load audit ledger', e);
      }
    };
    fetchAudit();
  }, [selectedIncidentId]);

  const handleUnitStatusChange = async (unitId: string, newStatus: string) => {
    if (newStatus === 'AVAILABLE') {
      const confirmed = window.confirm(
        'Clear this unit and return it to service?\n\nThis also resolves its linked incident and writes an audit entry.'
      );
      if (!confirmed) return;
    }

    setIsUpdating(true);
    setStatusMessage(null);
    try {
      const res = await fetch(`/api/v1/units/${unitId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: newStatus,
          dispatcher_id: 'UNIT_SIMULATOR_RADIO',
          notes: `Telemetry updated to ${newStatus}`
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to update unit status');
      }

      setStatusMessage({
        text: `Unit status transitioned to ${newStatus}. Associated incident updated.`,
        type: 'success'
      });
      await fetchData();
      if (selectedIncidentId) {
        const aRes = await fetch(`/api/v1/audit/${selectedIncidentId}`);
        if (aRes.ok) setAuditLogs(await aRes.json());
      }
    } catch (e: any) {
      setStatusMessage({ text: e.message || 'Status update error', type: 'error' });
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="h-[calc(100vh-4rem)] p-6 bg-slate-950 grid grid-cols-12 gap-6 overflow-hidden">
      {/* Left: Unit Simulator Control Panel */}
      <div className="col-span-12 lg:col-span-6 bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col overflow-hidden">
        <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
          <div className="flex items-center space-x-2">
            <Activity className="w-5 h-5 text-sky-400" />
            <h2 className="text-base font-bold text-white uppercase tracking-wider">
              Emergency Unit Telemetry Simulator
            </h2>
          </div>
          <button
            onClick={fetchData}
            aria-label="Refresh units and audit ledger"
            title="Refresh units and audit ledger"
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-all"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        <p className="text-xs text-slate-400 mb-4">
          Simulate responder Mobile Data Terminal (MDT) events. Changing unit status to <span className="font-bold text-purple-400">ON_SCENE</span> or <span className="font-bold text-emerald-400">AVAILABLE</span> advances the authoritative backend state machine.
        </p>

        {statusMessage && (
          <div
            role="status"
            className={`mb-4 p-3 rounded-xl border text-xs font-mono ${
              statusMessage.type === 'success'
                ? 'bg-emerald-950/60 border-emerald-800/60 text-emerald-300'
                : 'bg-rose-950/60 border-rose-800/60 text-rose-300'
            }`}
          >
            {statusMessage.text}
          </div>
        )}

        <div className="flex-1 overflow-y-auto space-y-3">
          {units.map((unit) => (
            <div
              key={unit.id}
              className="p-4 rounded-xl bg-slate-950/70 border border-slate-800 flex items-center justify-between"
            >
              <div>
                <div className="flex items-center space-x-2">
                  <span className="font-extrabold text-sm text-white">{unit.callsign}</span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-300 uppercase">
                    {unit.unit_type}
                  </span>
                </div>
                <div className="text-xs text-slate-400 mt-1">{unit.station}</div>
                <div className="text-[10px] font-mono text-slate-500 mt-0.5">
                  Location: {unit.latitude.toFixed(4)}, {unit.longitude.toFixed(4)}
                </div>
              </div>

              <div className="flex flex-col items-end space-y-2">
                <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded uppercase tracking-wider ${
                  unit.status === 'AVAILABLE'
                    ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/50'
                    : unit.status === 'ON_SCENE'
                    ? 'bg-purple-950/60 text-purple-400 border border-purple-800/50'
                    : 'bg-amber-950/60 text-amber-400 border border-amber-800/50'
                }`}>
                  {unit.status}
                </span>

                <div className="flex items-center space-x-1.5">
                  <button
                    onClick={() => handleUnitStatusChange(unit.id, 'ON_SCENE')}
                    disabled={isUpdating || unit.status !== 'DISPATCHED'}
                    title={
                      unit.status === 'DISPATCHED'
                        ? 'Mark this unit on scene'
                        : 'Only a dispatched unit can be marked on scene'
                    }
                    className="px-2.5 py-1 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-[11px] font-bold disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                  >
                    On Scene
                  </button>
                  <button
                    onClick={() => handleUnitStatusChange(unit.id, 'AVAILABLE')}
                    disabled={isUpdating || unit.status === 'AVAILABLE'}
                    title={
                      unit.status === 'AVAILABLE'
                        ? 'Unit is already available'
                        : 'Clear the unit and resolve its linked incident'
                    }
                    className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-bold disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                  >
                    Clear Scene
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right: Immutable Chronological Audit Ledger */}
      <div className="col-span-12 lg:col-span-6 bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col overflow-hidden">
        <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
          <div className="flex items-center space-x-2">
            <FileText className="w-5 h-5 text-emerald-400" />
            <h2 className="text-base font-bold text-white uppercase tracking-wider">
              Immutable Governance Audit Ledger
            </h2>
          </div>

          {/* Incident Selector */}
          <select
            value={selectedIncidentId}
            onChange={(e) => setSelectedIncidentId(e.target.value)}
            aria-label="Select incident for audit ledger"
            title="Select incident for audit ledger"
            className="p-2 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white font-mono"
          >
            {incidents.map((inc) => (
              <option key={inc.id} value={inc.id}>
                {inc.incident_number} ({inc.status})
              </option>
            ))}
          </select>
        </div>

        <p className="text-xs text-slate-400 mb-4">
          Append-only event ledger capturing state changes, AI assessments, and human dispatcher
          authorizations. Entries are ordered by server timestamp; this prototype does not use
          cryptographic sealing.
        </p>

        <div className="flex-1 overflow-y-auto space-y-3">
          {auditLogs.length === 0 ? (
            <div className="text-center py-16 text-slate-500 text-xs">
              No audit records discovered for this incident yet.
            </div>
          ) : (
            auditLogs.map((log, index) => {
              let parsedDetails: any = null;
              try {
                parsedDetails = JSON.parse(log.details);
              } catch {
                parsedDetails = log.details;
              }

              return (
                <div
                  key={log.id}
                  className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800/90 text-xs font-mono space-y-2"
                >
                  <div className="flex items-center justify-between border-b border-slate-800/60 pb-1.5">
                    <div className="flex items-center space-x-2">
                      <span className="w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center text-[10px] text-slate-300 font-bold">
                        {index + 1}
                      </span>
                      <span className="font-extrabold text-sky-400">{log.action}</span>
                    </div>
                    <span className="text-[10px] text-slate-500 flex items-center space-x-1">
                      <Clock className="w-3 h-3" />
                      <span>{new Date(log.timestamp).toLocaleTimeString()}</span>
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-slate-400">
                    <div>
                      Actor: <span className="text-emerald-400 font-bold">{log.actor}</span>
                    </div>
                    <div className="text-slate-500 text-[10px]">
                      {new Date(log.timestamp).toISOString().split('T')[0]}
                    </div>
                  </div>

                  <div className="bg-slate-900/90 p-2 rounded-lg text-[11px] text-slate-300 overflow-x-auto whitespace-pre-wrap">
                    {typeof parsedDetails === 'object' ? JSON.stringify(parsedDetails, null, 2) : parsedDetails}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
