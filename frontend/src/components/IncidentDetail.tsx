import React, { useState, useEffect } from 'react';
import { 
  ShieldAlert, 
  MapPin, 
  Clock, 
  Truck, 
  Send, 
  FileText, 
  AlertTriangle, 
  CheckCircle, 
  Users, 
  Flame, 
  Activity, 
  CheckCheck,
  RotateCw
} from 'lucide-react';
import { Incident, RecommendationResponse, CandidateUnit, ExtractedFacts } from '../types';
import { api } from '../services/api';

interface IncidentDetailProps {
  incident: Incident | null;
  onRefreshIncident?: () => void;
  onOpenAuditLog?: (incidentId: string) => void;
}

export const IncidentDetail: React.FC<IncidentDetailProps> = ({
  incident,
  onRefreshIncident,
  onOpenAuditLog
}) => {
  const [recommendation, setRecommendation] = useState<RecommendationResponse | null>(null);
  const [isLoadingRecs, setIsLoadingRecs] = useState(false);
  const [selectedUnit, setSelectedUnit] = useState<CandidateUnit | null>(null);
  const [dispatcherId, setDispatcherId] = useState('DISPATCHER_SARAH');
  const [dispatchNotes, setDispatchNotes] = useState('');
  const [isDispatching, setIsDispatching] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [actionMessage, setActionMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // Parse assessment JSON if available
  let facts: ExtractedFacts = {};
  if (incident?.assessment_data) {
    try {
      facts = typeof incident.assessment_data === 'string' 
        ? JSON.parse(incident.assessment_data) 
        : incident.assessment_data;
    } catch {
      facts = {};
    }
  }

  // Load recommendations whenever incident changes
  useEffect(() => {
    if (!incident) {
      setRecommendation(null);
      setSelectedUnit(null);
      return;
    }

    if (incident.status === 'RECOMMENDED' || incident.status === 'ASSESSED') {
      loadRecommendations(incident.id);
    } else {
      setRecommendation(null);
    }
  }, [incident?.id, incident?.status]);

  // Escape closes the dispatch confirmation modal, unless a request is in flight.
  useEffect(() => {
    if (!showConfirmModal) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !isDispatching) {
        setShowConfirmModal(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [showConfirmModal, isDispatching]);

  const loadRecommendations = async (incId: string) => {
    setIsLoadingRecs(true);
    try {
      const data = await api.getRecommendations(incId);
      setRecommendation(data);
      if (data.candidate_units.length > 0) {
        setSelectedUnit(data.candidate_units[0]);
      }
    } catch (err: any) {
      console.warn('Failed to load candidate units:', err.message);
    } finally {
      setIsLoadingRecs(false);
    }
  };

  const handleConfirmDispatch = async () => {
    if (!incident || !selectedUnit) return;
    setIsDispatching(true);
    setActionMessage(null);
    try {
      await api.approveDispatch(
        incident.id,
        selectedUnit.unit_id,
        dispatcherId,
        dispatchNotes || `Immediate deployment to ${incident.category} scene`
      );
      setActionMessage({
        text: `Unit ${selectedUnit.callsign} successfully dispatched to ${incident.incident_number}!`,
        type: 'success'
      });
      setShowConfirmModal(false);
      if (onRefreshIncident) onRefreshIncident();
    } catch (err: any) {
      setActionMessage({ text: err.message, type: 'error' });
    } finally {
      setIsDispatching(false);
    }
  };

  const handleQuickStatusTransition = async (targetStatus: 'ON_SCENE' | 'RESOLVED') => {
    if (!incident) return;

    // Never guess a unit: only the unit actually assigned to this incident may be
    // transitioned, otherwise a concurrent incident could be closed by mistake.
    const unitId = incident.assigned_unit_id;
    if (!unitId) {
      setActionMessage({
        text: 'No assigned unit recorded for this incident. Approve a dispatch first.',
        type: 'error'
      });
      return;
    }

    if (targetStatus === 'RESOLVED') {
      const confirmed = window.confirm(
        'Mark this incident as RESOLVED and return the assigned unit to service?\n\nThis writes an audit entry and cannot be undone from this panel.'
      );
      if (!confirmed) return;
    }

    try {
      await api.updateUnitStatus(
        unitId,
        targetStatus,
        dispatcherId,
        `Dispatcher status transition to ${targetStatus}`
      );
      setActionMessage({
        text:
          targetStatus === 'ON_SCENE'
            ? 'Unit marked on scene. Incident state advanced.'
            : 'Unit cleared and incident resolved.',
        type: 'success'
      });
      if (onRefreshIncident) onRefreshIncident();
    } catch (err: any) {
      setActionMessage({ text: err.message, type: 'error' });
    }
  };

  if (!incident) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8 text-center bg-slate-900 border border-slate-800 rounded-xl text-slate-400 space-y-3">
        <Activity className="w-12 h-12 text-slate-600 animate-pulse" />
        <h3 className="text-base font-semibold text-slate-200">No Emergency Selected</h3>
        <p className="text-xs text-slate-500 max-w-xs">
          Select an emergency incident from the left triage queue to review AI extraction facts, run spatial proximity calculations, and authorize dispatch.
        </p>
      </div>
    );
  }

  const isCritical = incident.severity === 'LEVEL_1_CRITICAL';

  return (
    <div className="h-full flex flex-col bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
      {/* Header Banner */}
      <div className="p-4 border-b border-slate-800 bg-slate-950/60 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-base font-bold text-white tracking-wider">
              {incident.incident_number}
            </span>
            <span
              className={`text-xs px-2.5 py-0.5 rounded-full font-bold border ${
                isCritical
                  ? 'bg-rose-950 text-rose-300 border-rose-500/50 animate-pulse'
                  : 'bg-amber-950 text-amber-300 border-amber-500/50'
              }`}
            >
              {incident.severity}
            </span>
            <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
              {incident.category}
            </span>
          </div>

          <div className="flex items-center gap-3 text-xs text-slate-400 mt-1.5">
            <span className="flex items-center gap-1">
              <MapPin className="w-3.5 h-3.5 text-slate-500" />
              {incident.address || `${incident.latitude.toFixed(4)}, ${incident.longitude.toFixed(4)}`}
            </span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-slate-500" />
              {incident.created_at ? new Date(incident.created_at).toLocaleString() : 'Recent'}
            </span>
          </div>
        </div>

        {onOpenAuditLog && (
          <button
            onClick={() => onOpenAuditLog(incident.id)}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-semibold flex items-center gap-1.5 transition"
          >
            <FileText className="w-3.5 h-3.5 text-rose-400" />
            <span>Audit Ledger</span>
          </button>
        )}
      </div>

      {/* Main Content Scrollable Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Action message feedback */}
        {actionMessage && (
          <div
            className={`p-3 rounded-lg text-xs font-medium flex items-center gap-2 ${
              actionMessage.type === 'success'
                ? 'bg-emerald-950/80 text-emerald-200 border border-emerald-500/50'
                : 'bg-rose-950/80 text-rose-200 border border-rose-500/50'
            }`}
          >
            {actionMessage.type === 'success' ? (
              <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
            )}
            <span>{actionMessage.text}</span>
          </div>
        )}

        {/* Potential Duplicate Report Banner */}
        {facts.potential_duplicate_of && (
          <div className="p-3 rounded-lg bg-amber-950/60 border border-amber-500/50 text-amber-200 text-xs space-y-1">
            <div className="flex items-center gap-2 font-bold text-amber-300">
              <AlertTriangle className="w-4 h-4 text-amber-400 animate-bounce" />
              <span>POTENTIAL DUPLICATE REPORT DETECTED</span>
            </div>
            <p className="text-[11px] text-amber-300/90 leading-relaxed">
              Spatial proximity match (~{facts.potential_duplicate_distance_meters ?? '<250'}m) with active incident{' '}
              <span className="font-mono font-bold text-white bg-amber-900/60 px-1.5 py-0.5 rounded border border-amber-400/40">
                {facts.potential_duplicate_of}
              </span>
              . Preserved distinctly in compliance with 112 multi-caller protocols.
            </p>
          </div>
        )}

        {/* Human Review Banner if required */}
        {incident.requires_human_review && (
          <div className="p-3 rounded-lg bg-rose-950/50 border border-rose-500/40 text-rose-200 text-xs space-y-1">
            <div className="flex items-center gap-2 font-bold text-rose-300">
              <ShieldAlert className="w-4 h-4 text-rose-400 animate-pulse" />
              <span>Mandatory Human-in-the-Loop Validation Required</span>
            </div>
            <p className="text-[11px] text-rose-300/80">
              AI inference triggered uncertainty protocols or critical life-safety hazards. Dispatcher sign-off is mandated before deployment.
            </p>
          </div>
        )}

        {/* Raw Caller Narrative */}
        <div className="bg-slate-950 rounded-lg p-3 border border-slate-800/80 space-y-1.5">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Emergency Caller Narrative / Speech Transcript
          </div>
          <p className="text-xs text-slate-200 leading-relaxed italic">
            "{incident.description}"
          </p>
        </div>

        {/* Structured AI Facts */}
        <div className="bg-slate-950 rounded-lg p-3 border border-slate-800/80 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              Semantic Entity Extraction &amp; Safety Signals
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-950/60 text-purple-300 border border-purple-500/30 normal-case tracking-normal">
                AI-generated
              </span>
            </span>
            <span
              className="text-[10px] px-2 py-0.5 rounded bg-purple-950/60 text-purple-300 border border-purple-500/30"
              title="Model-reported confidence is not a calibrated probability"
            >
              {typeof facts.confidence_score === 'number'
                ? `AI confidence: ${(facts.confidence_score * 100).toFixed(0)}% (model-reported)`
                : 'AI confidence: not reported'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="p-2.5 rounded bg-slate-900 border border-slate-800 flex items-center gap-2.5">
              <Users className="w-4 h-4 text-sky-400 flex-shrink-0" />
              <div>
                <div className="text-[10px] text-slate-400 uppercase">Casualty Count</div>
                <div className="font-bold text-slate-100">{facts.casualty_count ?? 'Unconfirmed'}</div>
              </div>
            </div>

            <div className="p-2.5 rounded bg-slate-900 border border-slate-800 flex items-center gap-2.5">
              <Flame className="w-4 h-4 text-rose-400 flex-shrink-0" />
              <div>
                <div className="text-[10px] text-slate-400 uppercase">Primary Hazards</div>
                <div className="font-bold text-slate-100 truncate">
                  {facts.hazards && facts.hazards.length > 0 ? facts.hazards.join(', ') : 'None Reported'}
                </div>
              </div>
            </div>
          </div>

          {/* Missing info flags */}
          {facts.missing_information && facts.missing_information.length > 0 && (
            <div className="space-y-1">
              <div className="text-[10px] font-semibold text-amber-400 uppercase">Information Deficits</div>
              <div className="flex flex-wrap gap-1.5">
                {facts.missing_information.map((info, idx) => (
                  <span key={idx} className="text-[10px] px-2 py-0.5 rounded bg-amber-950/40 text-amber-300 border border-amber-500/30">
                    ⚠ {info}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Uncertainty flags */}
          {facts.uncertainty_flags && facts.uncertainty_flags.length > 0 && (
            <div className="space-y-1">
              <div className="text-[10px] font-semibold text-rose-400 uppercase">Uncertainty Diagnostics</div>
              <div className="flex flex-wrap gap-1.5">
                {facts.uncertainty_flags.map((flag, idx) => (
                  <span key={idx} className="text-[10px] px-2 py-0.5 rounded bg-rose-950/40 text-rose-300 border border-rose-500/30 font-mono">
                    {flag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Spatial Unit Recommendation Section */}
        <div className="bg-slate-950 rounded-lg p-3 border border-slate-800/80 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                PostGIS Proximity &amp; Tactical Matching
              </h4>
              <p className="text-[10px] text-slate-400">
                Ranked by geodesic distance; travel time uses a fixed 40 km/h model (not live routing)
              </p>
            </div>
            
            <button
              onClick={() => loadRecommendations(incident.id)}
              disabled={isLoadingRecs}
              className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs transition"
              title="Recalculate Proximity"
            >
              <RotateCw className={`w-3.5 h-3.5 ${isLoadingRecs ? 'animate-spin text-rose-400' : ''}`} />
            </button>
          </div>

          {isLoadingRecs ? (
            <div className="p-4 text-center text-xs text-slate-400 space-y-2">
              <div className="w-5 h-5 border-2 border-rose-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
              <p>Executing PostGIS distance query...</p>
            </div>
          ) : recommendation && recommendation.candidate_units.length > 0 ? (
            <div className="space-y-2">
              <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-[11px] text-slate-300 leading-relaxed">
                <span className="font-bold text-rose-400">Tactical Rationale:</span> {recommendation.rationale}
              </div>

              <div className="space-y-1.5">
                {recommendation.candidate_units.map((unit, idx) => {
                  const isSelected = selectedUnit?.unit_id === unit.unit_id;
                  return (
                    <div
                      key={unit.unit_id}
                      onClick={() => setSelectedUnit(unit)}
                      className={`p-2.5 rounded-lg border cursor-pointer transition flex items-center justify-between gap-3 ${
                        isSelected
                          ? 'bg-rose-950/40 border-rose-500/60 shadow-md ring-1 ring-rose-500/30'
                          : 'bg-slate-900 border-slate-800 hover:bg-slate-800/80'
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <div className="w-6 h-6 rounded bg-slate-800 border border-slate-700 text-xs flex items-center justify-center font-bold text-slate-300">
                          #{idx + 1}
                        </div>
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono font-bold text-xs text-white">{unit.callsign}</span>
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-300">
                              {unit.type}
                            </span>
                          </div>
                          <div className="text-[10px] text-slate-400">{unit.station || 'Local Station'}</div>
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="text-xs font-bold text-emerald-400">
                          ~{unit.eta_minutes} min <span className="font-normal text-slate-400">est.</span>
                        </div>
                        <div className="text-[10px] text-slate-400">{unit.distance_km} km straight-line</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="p-4 rounded-lg bg-rose-950/40 border-2 border-rose-600/80 text-rose-200 text-xs space-y-2">
              <div className="flex items-center gap-2 font-bold text-rose-300 text-sm">
                <AlertTriangle className="w-5 h-5 text-rose-400 animate-pulse" />
                <span>CRITICAL RESOURCE SHORTAGE</span>
              </div>
              <p className="text-xs text-rose-200 font-medium leading-relaxed">
                No units currently AVAILABLE. Mutual aid escalation required.
              </p>
              <div className="text-[11px] text-slate-300 bg-slate-950/80 p-2 rounded border border-slate-800">
                Contact neighboring district dispatch or mutual aid coordinator to request inter-jurisdictional ambulance / fire assistance.
              </div>
            </div>
          )}
        </div>

        {/* Human Dispatch Authorization Action */}
        {['REPORTED', 'ASSESSED', 'RECOMMENDED'].includes(incident.status) && (
          <div className="bg-gradient-to-br from-slate-950 to-rose-950/30 rounded-xl p-4 border border-rose-500/30 space-y-3">
            <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Send className="w-4 h-4 text-rose-400" />
              <span>Human Dispatch Authorization Gate</span>
            </h4>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <label className="text-[10px] text-slate-400 uppercase font-semibold">Dispatcher ID</label>
                <input
                  type="text"
                  value={dispatcherId}
                  onChange={(e) => setDispatcherId(e.target.value)}
                  className="w-full mt-1 bg-slate-900 text-xs text-slate-200 px-3 py-1.5 rounded border border-slate-700 focus:outline-none focus:border-rose-500 font-mono"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 uppercase font-semibold">Deployment Order Notes</label>
                <input
                  type="text"
                  value={dispatchNotes}
                  onChange={(e) => setDispatchNotes(e.target.value)}
                  placeholder="e.g. Code 3 sirens authorized"
                  className="w-full mt-1 bg-slate-900 text-xs text-slate-200 px-3 py-1.5 rounded border border-slate-700 focus:outline-none focus:border-rose-500"
                />
              </div>
            </div>

            <button
              onClick={() => setShowConfirmModal(true)}
              disabled={isDispatching || !selectedUnit}
              className="w-full py-2.5 rounded-lg bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 disabled:opacity-50 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-xl shadow-rose-950/50 transition ring-1 ring-rose-400/50"
            >
              <CheckCheck className="w-4 h-4" />
              <span>
                {isDispatching 
                  ? 'Authorizing Deployment...' 
                  : `Confirm & Dispatch ${selectedUnit?.callsign || 'Selected Unit'}`}
              </span>
            </button>
          </div>
        )}

        {/* Dispatch Confirmation Modal */}
        {showConfirmModal && selectedUnit && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="dispatch-confirm-title"
              className="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl animate-in fade-in zoom-in-95"
            >
              <div className="flex items-center gap-3 border-b border-slate-800 pb-3">
                <div className="w-10 h-10 rounded-xl bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-400">
                  <ShieldAlert className="w-6 h-6" />
                </div>
                <div>
                  <h3 id="dispatch-confirm-title" className="text-sm font-bold text-white uppercase tracking-wider">Confirm Dispatch Order</h3>
                  <p className="text-xs text-slate-400">Human Dispatcher Authorization Protocol</p>
                </div>
              </div>

              <div className="space-y-2 text-xs bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                <div className="flex justify-between">
                  <span className="text-slate-400">Incident Target:</span>
                  <span className="font-mono font-bold text-white">{incident.incident_number}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Selected Unit:</span>
                  <span className="font-mono font-bold text-rose-400">{selectedUnit.callsign} ({selectedUnit.type})</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Estimated Distance:</span>
                  <span className="font-mono text-slate-200">{selectedUnit.distance_km} km</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Est. travel (40 km/h model):</span>
                  <span className="font-mono font-bold text-emerald-400">~{selectedUnit.eta_minutes} minutes</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Authorizing Officer:</span>
                  <span className="font-mono text-slate-300">{dispatcherId}</span>
                </div>
              </div>

              <p className="text-[11px] text-slate-400 leading-relaxed">
                By confirming, you authorize deployment of this simulated emergency unit. The unit
                status will transition to <span className="font-bold text-amber-400">DISPATCHED</span> and an
                audit log entry will be recorded. No unit is dispatched autonomously.
              </p>

              <div className="grid grid-cols-2 gap-3 pt-2">
                <button
                  onClick={() => setShowConfirmModal(false)}
                  className="py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold text-xs transition"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirmDispatch}
                  disabled={isDispatching}
                  className="py-2.5 rounded-xl bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 text-white font-bold text-xs shadow-lg shadow-rose-950 transition flex items-center justify-center gap-1.5"
                >
                  <CheckCheck className="w-4 h-4" />
                  <span>{isDispatching ? 'Transmitting...' : 'Authorize Dispatch'}</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Live MDT Crew Status Controls (if Dispatched or On Scene) */}
        {['DISPATCHED', 'ON_SCENE'].includes(incident.status) && (
          <div className="bg-slate-950 rounded-xl p-4 border border-amber-500/40 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-2">
                <Truck className="w-4 h-4 text-amber-400" />
                <span>Unit Deployment MDT Live Tracking</span>
              </h4>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-500/50 animate-pulse">
                {incident.status}
              </span>
            </div>

            {incident.assigned_unit_callsign && (
              <div className="p-3 bg-slate-900 border border-slate-800 rounded-lg flex items-center justify-between text-xs">
                <div>
                  <span className="text-[10px] text-slate-400 block font-semibold uppercase">Assigned Unit</span>
                  <span className="font-mono font-bold text-white text-sm">{incident.assigned_unit_callsign}</span>
                  <span className="text-[10px] ml-2 px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-bold uppercase">
                    {incident.assigned_unit_type || 'AMBULANCE'}
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-[10px] text-amber-400 font-bold font-mono">MISSION ACTIVE</span>
                </div>
              </div>
            )}

            <p className="text-[11px] text-slate-400">
              Simulate responding vehicle geofence arrival or crew operational sign-off:
            </p>

            <div className="grid grid-cols-2 gap-2 text-xs">
              {incident.status === 'DISPATCHED' && (
                <button
                  onClick={() => handleQuickStatusTransition('ON_SCENE')}
                  className="py-2 rounded-lg bg-purple-700 hover:bg-purple-600 text-white font-bold transition flex items-center justify-center gap-2"
                >
                  <span>Mark Unit On-Scene</span>
                </button>
              )}

              <button
                onClick={() => handleQuickStatusTransition('RESOLVED')}
                className="py-2 rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white font-bold transition flex items-center justify-center gap-2"
              >
                <span>Incident Mitigated / Resolved</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
