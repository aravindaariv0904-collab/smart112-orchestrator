import React from 'react';
import { ShieldAlert, AlertTriangle, UserCheck, CheckCircle2, MapPin, Zap } from 'lucide-react';
import { MapIncident } from '../map/LeafletMap';

interface IncidentDetailProps {
  incident: MapIncident | null;
}

export const IncidentDetail: React.FC<IncidentDetailProps> = ({ incident }) => {
  if (!incident) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-8 text-slate-500">
        <ShieldAlert className="w-12 h-12 text-slate-700 mb-3" />
        <p className="text-sm font-medium">Select an incident from the queue to view AI triage assessment and operational telemetry.</p>
      </div>
    );
  }

  // Parse assessment data if available
  let assessment: any = {};
  try {
    assessment = JSON.parse((incident as any).assessment_data || '{}');
  } catch {
    assessment = {};
  }

  const hazards: string[] = assessment.hazards || [];
  const missingInfo: string[] = assessment.missing_information || [];
  const confidenceScore = assessment.confidence_score ? Math.round(assessment.confidence_score * 100) : 85;

  return (
    <div className="flex flex-col h-full bg-slate-900 overflow-y-auto p-4 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-slate-800 pb-3">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-lg font-extrabold text-white tracking-tight">{incident.incident_number}</h1>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider bg-red-500/20 text-red-400 border border-red-500/30">
              {incident.severity}
            </span>
          </div>
          <div className="flex items-center text-xs text-slate-400 mt-1 space-x-2">
            <MapPin className="w-3.5 h-3.5 text-slate-500" />
            <span>Lat: {incident.latitude.toFixed(4)}, Lng: {incident.longitude.toFixed(4)}</span>
          </div>
        </div>

        <div className="text-right">
          <span className="text-[10px] text-slate-400 block font-semibold uppercase">Current State</span>
          <span className="text-xs font-bold text-sky-400 bg-sky-950/60 border border-sky-800 px-2 py-0.5 rounded uppercase">
            {incident.status}
          </span>
        </div>
      </div>

      {/* Raw Emergency Transcript */}
      <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800">
        <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5 flex items-center space-x-1.5">
          <Zap className="w-3.5 h-3.5 text-amber-400" />
          <span>Ingested Emergency Intake Transcript</span>
        </div>
        <p className="text-xs text-slate-200 leading-relaxed font-mono">
          "{incident.description}"
        </p>
      </div>

      {/* AI Extraction Cards */}
      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
            Assessed Casualties
          </span>
          <div className="text-xl font-extrabold text-white">
            {assessment.casualty_count ?? 0} <span className="text-xs text-slate-400 font-normal">victim(s)</span>
          </div>
        </div>

        <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
            Model Confidence
          </span>
          <div className="text-xl font-extrabold text-emerald-400 flex items-center space-x-1.5">
            <span>{confidenceScore}%</span>
            <span className="text-[10px] text-slate-400 font-normal">(Free Tier Gemini)</span>
          </div>
        </div>
      </div>

      {/* Active Hazards */}
      {hazards.length > 0 && (
        <div className="p-3 rounded-xl bg-red-950/20 border border-red-900/40">
          <div className="text-[11px] font-bold text-red-400 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
            <span>Identified On-Scene Hazards</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {hazards.map((hazard, idx) => (
              <span
                key={idx}
                className="text-[10px] font-bold px-2 py-0.5 rounded bg-red-900/50 text-red-200 border border-red-700/50 uppercase"
              >
                {hazard.replace('_', ' ')}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Missing Information Alerts */}
      {missingInfo.length > 0 && (
        <div className="p-3 rounded-xl bg-amber-950/20 border border-amber-900/40">
          <div className="text-[11px] font-bold text-amber-400 uppercase tracking-wider mb-1.5 flex items-center space-x-1.5">
            <UserCheck className="w-3.5 h-3.5 text-amber-400" />
            <span>Operational Gaps (Dispatcher Verification Needed)</span>
          </div>
          <ul className="text-xs text-amber-200/90 space-y-1 list-disc list-inside">
            {missingInfo.map((item, idx) => (
              <li key={idx} className="font-medium">{item}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
