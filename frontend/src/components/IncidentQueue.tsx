import React from 'react';
import { AlertCircle, Clock, MapPin, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { MapIncident } from '../map/LeafletMap';

interface IncidentQueueProps {
  incidents: MapIncident[];
  selectedIncidentId: string | null;
  onSelectIncident: (incident: MapIncident) => void;
  isLoading?: boolean;
}

export const IncidentQueue: React.FC<IncidentQueueProps> = ({
  incidents,
  selectedIncidentId,
  onSelectIncident,
  isLoading
}) => {
  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'LEVEL_1_CRITICAL':
        return 'bg-red-500/20 text-red-400 border-red-500/40 animate-pulse';
      case 'LEVEL_2_HIGH':
        return 'bg-orange-500/20 text-orange-400 border-orange-500/40';
      case 'LEVEL_3_MODERATE':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/40';
      case 'LEVEL_4_LOW':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/40';
      default:
        return 'bg-slate-500/20 text-slate-400 border-slate-500/40';
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'REPORTED':
      case 'ASSESSED':
        return 'text-amber-400 bg-amber-950/40 border-amber-800/40';
      case 'RECOMMENDED':
        return 'text-sky-400 bg-sky-950/40 border-sky-800/40';
      case 'DISPATCHED':
        return 'text-indigo-400 bg-indigo-950/40 border-indigo-800/40';
      case 'ON_SCENE':
        return 'text-purple-400 bg-purple-950/40 border-purple-800/40';
      case 'RESOLVED':
        return 'text-emerald-400 bg-emerald-950/40 border-emerald-800/40';
      default:
        return 'text-slate-400 bg-slate-900 border-slate-800';
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-900 border-r border-slate-800">
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-red-500" />
          <h2 className="font-bold text-sm tracking-wide text-slate-100 uppercase">Emergency Incident Queue</h2>
        </div>
        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 font-mono text-slate-300">
          {incidents.length} Active
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {isLoading && incidents.length === 0 ? (
          <div className="text-center py-10 text-slate-500 text-xs">Polling incidents...</div>
        ) : incidents.length === 0 ? (
          <div className="text-center py-12 text-slate-500 text-xs">
            No active emergencies in queue. All clear.
          </div>
        ) : (
          incidents.map((incident) => {
            const isSelected = incident.id === selectedIncidentId;
            return (
              <div
                key={incident.id}
                onClick={() => onSelectIncident(incident)}
                className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-slate-800/90 border-red-500/80 shadow-lg shadow-red-950/40 translate-x-1'
                    : 'bg-slate-950/60 border-slate-800/80 hover:bg-slate-800/40 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-xs font-bold text-slate-300 tracking-wider">
                    {incident.incident_number}
                  </span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase ${getSeverityBadge(incident.severity)}`}>
                    {incident.severity.replace('LEVEL_', 'L')}
                  </span>
                </div>

                <p className="text-xs text-slate-200 line-clamp-2 font-medium mb-3">
                  {incident.description}
                </p>

                <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-[11px]">
                  <span className="text-slate-400 font-semibold uppercase tracking-wider">
                    {incident.category}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase tracking-wider ${getStatusBadge(incident.status)}`}>
                    {incident.status}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
