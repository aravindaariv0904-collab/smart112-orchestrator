import React, { useState, useEffect } from 'react';
import { IncidentQueue } from '../components/IncidentQueue';
import { IncidentDetail } from '../components/IncidentDetail';
import { UnitRecommendations, CandidateUnit } from '../components/UnitRecommendations';
import { LeafletMap, MapIncident, MapUnit } from '../map/LeafletMap';

export const DispatcherDashboard: React.FC = () => {
  const [incidents, setIncidents] = useState<MapIncident[]>([]);
  const [units, setUnits] = useState<MapUnit[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<MapIncident | null>(null);
  const [candidates, setCandidates] = useState<CandidateUnit[]>([]);
  const [rationale, setRationale] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Poll active incidents and units
  const fetchDashboardData = async () => {
    try {
      const [incRes, unitRes] = await Promise.all([
        fetch('/api/v1/incidents'),
        fetch('/api/v1/units')
      ]);

      if (incRes.ok) {
        const incData: MapIncident[] = await incRes.json();
        setIncidents(incData);

        // Retain or select first active incident
        if (!selectedIncident && incData.length > 0) {
          setSelectedIncident(incData[0]);
        } else if (selectedIncident) {
          const updated = incData.find(i => i.id === selectedIncident.id);
          if (updated) setSelectedIncident(updated);
        }
      }

      if (unitRes.ok) {
        const unitData: MapUnit[] = await unitRes.json();
        setUnits(unitData);
      }
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const timer = setInterval(fetchDashboardData, 4000);
    return () => clearInterval(timer);
  }, [selectedIncident?.id]);

  // Fetch recommendations when selected incident changes
  useEffect(() => {
    if (!selectedIncident) {
      setCandidates([]);
      setRationale('');
      return;
    }

    const fetchRecommendations = async () => {
      try {
        const res = await fetch(`/api/v1/incidents/${selectedIncident.id}/recommend`, {
          method: 'POST'
        });
        if (res.ok) {
          const data = await res.json();
          setCandidates(data.candidate_units || []);
          setRationale(data.rationale || '');
        }
      } catch (err) {
        console.error('Error fetching recommendations:', err);
      }
    };

    fetchRecommendations();
  }, [selectedIncident?.id]);

  // Handle Dispatch Approval from UI
  const handleDispatchApproved = async (unitId: string) => {
    if (!selectedIncident) return;
    const res = await fetch(`/api/v1/incidents/${selectedIncident.id}/approve-dispatch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        unit_id: unitId,
        dispatcher_id: 'DISPATCHER_LEAD_01',
        notes: 'Priority dispatch confirmed via Dispatcher Console'
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Dispatch approval rejected');
    }

    // Refresh immediately
    await fetchDashboardData();
  };

  // Find assigned unit for route rendering if incident is dispatched
  const assignedUnit = (selectedIncident?.status === 'DISPATCHED' || selectedIncident?.status === 'ON_SCENE')
    ? units.find(u => u.status === 'DISPATCHED' || u.status === 'ON_SCENE') || null
    : null;

  return (
    <div className="h-[calc(100vh-4rem)] grid grid-cols-12 overflow-hidden bg-slate-950">
      {/* Column 1: Incident Queue (3 cols) */}
      <div className="col-span-12 md:col-span-3 h-full overflow-hidden">
        <IncidentQueue
          incidents={incidents}
          selectedIncidentId={selectedIncident?.id || null}
          onSelectIncident={(inc) => setSelectedIncident(inc)}
          isLoading={isLoading}
        />
      </div>

      {/* Column 2: Incident Review & AI Triage & Recommendations (4 cols) */}
      <div className="col-span-12 md:col-span-4 h-full border-r border-slate-800 flex flex-col justify-between overflow-hidden">
        <div className="flex-1 overflow-y-auto">
          <IncidentDetail incident={selectedIncident} />
        </div>
        <div className="border-t border-slate-800">
          <UnitRecommendations
            incidentId={selectedIncident?.id || null}
            candidates={candidates}
            rationale={rationale}
            onDispatchApproved={handleDispatchApproved}
          />
        </div>
      </div>

      {/* Column 3: Leaflet Operations Map (5 cols) */}
      <div className="col-span-12 md:col-span-5 h-full p-4 flex flex-col">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-ping" />
            <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-200">
              Live Spatial Tactical Operations Map
            </h2>
          </div>
          <span className="text-[10px] text-slate-400 font-mono">
            {units.filter(u => u.status === 'AVAILABLE').length} Units Available
          </span>
        </div>
        <div className="flex-1">
          <LeafletMap
            center={selectedIncident ? [selectedIncident.latitude, selectedIncident.longitude] : [16.3067, 80.4365]}
            incidents={incidents}
            units={units}
            activeIncident={selectedIncident}
            assignedUnit={assignedUnit}
          />
        </div>
      </div>
    </div>
  );
};
