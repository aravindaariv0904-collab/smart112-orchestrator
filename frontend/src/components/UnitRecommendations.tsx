import React, { useState } from 'react';
import { Send, Navigation, Clock, ShieldCheck, XCircle, AlertCircle } from 'lucide-react';

export interface CandidateUnit {
  unit_id: string;
  callsign: string;
  type: string;
  distance_km: number;
  eta_minutes: number;
  status: string;
  station?: string;
  latitude: number;
  longitude: number;
}

interface UnitRecommendationsProps {
  incidentId: string | null;
  candidates: CandidateUnit[];
  rationale: string;
  onDispatchApproved: (unitId: string) => Promise<void>;
  isLoading?: boolean;
}

export const UnitRecommendations: React.FC<UnitRecommendationsProps> = ({
  incidentId,
  candidates,
  rationale,
  onDispatchApproved,
  isLoading
}) => {
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  // Default to first candidate if not manually selected
  const activeUnitId = selectedUnitId || (candidates.length > 0 ? candidates[0].unit_id : null);

  const handleApprove = async () => {
    if (!incidentId || !activeUnitId) return;
    setIsSubmitting(true);
    setFeedback(null);
    try {
      await onDispatchApproved(activeUnitId);
      setFeedback('Dispatch order successfully validated and broadcast by backend.');
    } catch (err: any) {
      setFeedback(err.message || 'Dispatch authorization failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!incidentId) {
    return null;
  }

  return (
    <div className="p-4 bg-slate-900 border-t border-slate-800 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Navigation className="w-4 h-4 text-sky-400" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
            PostGIS Spatial Unit Recommendations
          </h3>
        </div>
        <span className="text-[10px] text-slate-400 font-mono">
          Model: 40 km/h Urban Velocity
        </span>
      </div>

      {/* Rationale Bar */}
      {rationale && (
        <div className="p-2.5 rounded-lg bg-sky-950/30 border border-sky-800/40 text-xs text-sky-200 leading-snug">
          <span className="font-bold text-sky-400">Tactical Pairing Rationale: </span>
          {rationale}
        </div>
      )}

      {/* Candidates List */}
      <div className="space-y-2 max-h-48 overflow-y-auto">
        {candidates.map((unit, index) => {
          const isSelected = unit.unit_id === activeUnitId;
          return (
            <div
              key={unit.unit_id}
              onClick={() => setSelectedUnitId(unit.unit_id)}
              className={`p-2.5 rounded-xl border flex items-center justify-between cursor-pointer transition-all ${
                isSelected
                  ? 'bg-sky-950/40 border-sky-500 shadow-md shadow-sky-950/50'
                  : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center space-x-3">
                <div className={`w-6 h-6 rounded-lg flex items-center justify-center text-xs font-bold ${
                  index === 0 ? 'bg-red-500/20 text-red-400 border border-red-500/40' : 'bg-slate-800 text-slate-400'
                }`}>
                  #{index + 1}
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-bold text-white">{unit.callsign}</span>
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 font-mono">
                      {unit.type}
                    </span>
                  </div>
                  <span className="text-[11px] text-slate-400">{unit.station}</span>
                </div>
              </div>

              <div className="text-right flex items-center space-x-3">
                <div>
                  <div className="text-xs font-bold text-emerald-400 flex items-center justify-end space-x-1">
                    <Clock className="w-3 h-3" />
                    <span>{unit.eta_minutes}m ETA</span>
                  </div>
                  <span className="text-[10px] text-slate-400">{unit.distance_km} km away</span>
                </div>
                <input
                  type="radio"
                  name="unit_selection"
                  checked={isSelected}
                  onChange={() => setSelectedUnitId(unit.unit_id)}
                  className="accent-sky-500 cursor-pointer"
                />
              </div>
            </div>
          );
        })}
      </div>

      {feedback && (
        <div className="text-xs p-2 rounded bg-slate-950 border border-slate-800 text-emerald-400 font-mono">
          {feedback}
        </div>
      )}

      {/* Action Controls */}
      <div className="flex items-center space-x-2 pt-2">
        <button
          onClick={handleApprove}
          disabled={!activeUnitId || isSubmitting}
          className="flex-1 flex items-center justify-center space-x-2 py-2.5 px-4 rounded-xl bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white font-bold text-xs shadow-lg shadow-red-950/50 disabled:opacity-50 transition-all cursor-pointer"
        >
          <Send className="w-4 h-4" />
          <span>{isSubmitting ? 'Validating Dispatch...' : 'Approve & Dispatch Unit'}</span>
        </button>

        <button
          onClick={() => {
            const nextIdx = (candidates.findIndex(c => c.unit_id === activeUnitId) + 1) % candidates.length;
            if (candidates[nextIdx]) setSelectedUnitId(candidates[nextIdx].unit_id);
          }}
          className="px-3 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-all"
        >
          Next Candidate
        </button>
      </div>
    </div>
  );
};
