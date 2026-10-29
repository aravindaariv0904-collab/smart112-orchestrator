import React, { useState, useEffect, useRef } from 'react';
import { Header, PortalTab } from './components/Header';
import { IncidentList } from './components/IncidentList';
import { MapPane } from './components/MapPane';
import { IncidentDetail } from './components/IncidentDetail';
import { CallSimulatorModal } from './components/CallSimulatorModal';
import { UnitFleetModal } from './components/UnitFleetModal';
import { AuditLogDrawer } from './components/AuditLogDrawer';
import { AnalyticsDashboard } from './components/AnalyticsDashboard';
import { PublicPortal } from './views/PublicPortal';
import { ResponderMDT } from './views/ResponderMDT';
import { AuditView } from './views/AuditView';
import { Incident, EmergencyUnit } from './types';
import { api } from './services/api';

export function App() {
  const [activeTab, setActiveTab] = useState<PortalTab>('CAD');
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [units, setUnits] = useState<EmergencyUnit[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);
  const [isCallModalOpen, setIsCallModalOpen] = useState(false);
  const [isFleetModalOpen, setIsFleetModalOpen] = useState(false);
  const [auditIncidentId, setAuditIncidentId] = useState<string | null>(null);
  const requestInFlightRef = useRef(false);

  const loadData = async () => {
    // Skip overlapping polls; a slow request must not stack up.
    if (requestInFlightRef.current) return;
    requestInFlightRef.current = true;
    setIsLoading(true);
    try {
      const [fetchedIncidents, fetchedUnits] = await Promise.all([
        api.getIncidents(),
        api.getUnits()
      ]);
      setIncidents(fetchedIncidents);
      setUnits(fetchedUnits);
      setDataError(null);

      // Preserve or update selected incident
      if (selectedIncident) {
        const refreshed = fetchedIncidents.find(i => i.id === selectedIncident.id);
        if (refreshed) setSelectedIncident(refreshed);
      } else if (fetchedIncidents.length > 0) {
        setSelectedIncident(fetchedIncidents[0]);
      }
    } catch (err: any) {
      setDataError(err.message || 'Unable to reach the SMART 112 backend.');
    } finally {
      requestInFlightRef.current = false;
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const timer = setInterval(loadData, 5000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSimulateArrival = async (unitId: string) => {
    const confirmed = window.confirm(
      'Mark this assigned unit as ON SCENE?\n\nThis updates the unit and incident state machine and writes an audit entry.'
    );
    if (!confirmed) return;
    try {
      await api.updateUnitStatus(unitId, 'ON_SCENE', 'DISPATCHER_SARAH', 'Map quick action: on scene');
      await loadData();
    } catch (err: any) {
      setDataError(err.message || 'Failed to update unit status.');
    }
  };

  const handlePurgeQueue = async () => {
    if (confirm('Clear all active emergency incidents and reset portal to empty?')) {
      try {
        await api.purgeAllIncidents();
        setSelectedIncident(null);
        await loadData();
      } catch (err: any) {
        setDataError(err.message || 'Failed to clear incidents.');
      }
    }
  };

  const availableUnitsCount = units.filter(u => u.status === 'AVAILABLE').length;
  const activeEmergenciesCount = incidents.filter(i => !['RESOLVED', 'CANCELLED'].includes(i.status)).length;

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#080D1A] text-slate-100 font-sans selection:bg-rose-500 selection:text-white">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-[3000] focus:px-3 focus:py-2 focus:rounded-lg focus:bg-sky-600 focus:text-white focus:text-xs focus:font-bold"
      >
        Skip to main content
      </a>

      {/* Universal Top Header with Navigation Tabs */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenCallSimulator={() => setIsCallModalOpen(true)}
        onOpenFleetMonitor={() => setIsFleetModalOpen(true)}
        onRefresh={loadData}
        onPurgeQueue={handlePurgeQueue}
        isLoading={isLoading}
        activeCount={activeEmergenciesCount}
        availableUnitsCount={availableUnitsCount}
      />

      {dataError && (
        <div
          role="alert"
          className="flex items-start gap-2 px-4 py-2 bg-rose-950/80 border-b border-rose-700 text-rose-200 text-xs"
        >
          <span className="font-bold">Backend unavailable:</span>
          <span className="flex-1">{dataError}</span>
          <button
            type="button"
            onClick={loadData}
            className="underline font-semibold hover:text-white"
          >
            Retry
          </button>
        </div>
      )}

      {/* Main Tabbed Views */}
      <main id="main-content" className="flex-1 min-h-0 overflow-hidden">
        {/* Tab 1: CAD Dispatch Operations Command Center */}
        {activeTab === 'CAD' && (
          <div className="page-enter h-full grid grid-cols-1 md:grid-cols-12 gap-3 p-3 min-h-0 overflow-hidden">
            {/* Left: Triage Incident Queue (3 cols) */}
            <section className="col-span-12 md:col-span-3 h-full min-h-0 flex flex-col">
              <IncidentList
                incidents={incidents}
                selectedIncident={selectedIncident}
                onSelectIncident={(inc) => setSelectedIncident(inc)}
                isLoading={isLoading}
              />
            </section>

            {/* Center: OpenStreetMap GIS Cartography & Real-Time Moving Vehicle Telemetry (5 cols) */}
            <section className="col-span-12 md:col-span-5 h-full min-h-0 flex flex-col">
              <MapPane
                incidents={incidents}
                units={units}
                selectedIncident={selectedIncident}
                onSelectIncident={(inc) => setSelectedIncident(inc)}
                onSimulateArrival={handleSimulateArrival}
              />
            </section>

            {/* Right: AI Triage, Spatial Recommendations, and Human Dispatch Gate (4 cols) */}
            <section className="col-span-12 md:col-span-4 h-full min-h-0 flex flex-col">
              <IncidentDetail
                incident={selectedIncident}
                onRefreshIncident={loadData}
                onOpenAuditLog={(id) => setAuditIncidentId(id)}
              />
            </section>
          </div>
        )}

        {/* Tab 2: Citizen 112 Emergency Reporting Portal */}
        {activeTab === 'PUBLIC' && (
          <div className="page-enter h-full overflow-y-auto">
            <PublicPortal />
          </div>
        )}

        {/* Tab 3: Responder Mobile Data Terminal */}
        {activeTab === 'MDT' && (
          <div className="page-enter h-full overflow-y-auto">
            <ResponderMDT
              units={units}
              incidents={incidents}
              onRefresh={loadData}
            />
          </div>
        )}

        {/* Tab 4: Command Center Operations & Intelligence Analytics */}
        {activeTab === 'ANALYTICS' && (
          <div className="page-enter h-full overflow-y-auto">
            <AnalyticsDashboard
              incidents={incidents}
              units={units}
            />
          </div>
        )}

        {/* Tab 5: Audit Ledger & Governance History */}
        {activeTab === 'AUDIT' && (
          <div className="page-enter h-full overflow-y-auto">
            <AuditView />
          </div>
        )}
      </main>

      {/* Modals and Drawers */}
      <CallSimulatorModal
        isOpen={isCallModalOpen}
        onClose={() => setIsCallModalOpen(false)}
        onIncidentCreated={loadData}
      />

      <UnitFleetModal
        isOpen={isFleetModalOpen}
        onClose={() => setIsFleetModalOpen(false)}
        units={units}
        onRefreshUnits={loadData}
      />

      <AuditLogDrawer
        incidentId={auditIncidentId}
        isOpen={auditIncidentId !== null}
        onClose={() => setAuditIncidentId(null)}
      />
    </div>
  );
}

export default App;
