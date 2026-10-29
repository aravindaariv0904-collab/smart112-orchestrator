import React, { useState, useEffect } from 'react';
import { Header, PortalTab } from './components/Header';
import { IncidentList } from './components/IncidentList';
import { MapPane } from './components/MapPane';
import { IncidentDetail } from './components/IncidentDetail';
import { CallSimulatorModal } from './components/CallSimulatorModal';
import { UnitFleetModal } from './components/UnitFleetModal';
import { AuditLogDrawer } from './components/AuditLogDrawer';
import { AnalyticsDashboard } from './components/AnalyticsDashboard';
import { PublicPortal } from './views/PublicPortal';
import { AuditView } from './views/AuditView';
import { Incident, EmergencyUnit } from './types';
import { api } from './services/api';

export function App() {
  const [activeTab, setActiveTab] = useState<PortalTab>('CAD');
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [units, setUnits] = useState<EmergencyUnit[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isCallModalOpen, setIsCallModalOpen] = useState(false);
  const [isFleetModalOpen, setIsFleetModalOpen] = useState(false);
  const [auditIncidentId, setAuditIncidentId] = useState<string | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [fetchedIncidents, fetchedUnits] = await Promise.all([
        api.getIncidents(),
        api.getUnits()
      ]);
      setIncidents(fetchedIncidents);
      setUnits(fetchedUnits);

      // Preserve or update selected incident
      if (selectedIncident) {
        const refreshed = fetchedIncidents.find(i => i.id === selectedIncident.id);
        if (refreshed) setSelectedIncident(refreshed);
      } else if (fetchedIncidents.length > 0) {
        setSelectedIncident(fetchedIncidents[0]);
      }
    } catch (err: any) {
      console.warn('Data sync warning:', err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // Poll every 5 seconds for sub-second telemetry sync
    const timer = setInterval(() => {
      loadData();
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  const handlePurgeQueue = async () => {
    if (confirm('Clear all active emergency incidents and reset portal to empty?')) {
      try {
        await api.purgeAllIncidents();
        setSelectedIncident(null);
        await loadData();
      } catch (err: any) {
        console.error('Failed to purge incidents:', err);
      }
    }
  };

  const availableUnitsCount = units.filter(u => u.status === 'AVAILABLE').length;
  const activeEmergenciesCount = incidents.filter(i => !['RESOLVED', 'CANCELLED'].includes(i.status)).length;

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#080D1A] text-slate-100 font-sans selection:bg-rose-500 selection:text-white">
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

      {/* Main Tabbed Views */}
      <main className="flex-1 min-h-0 overflow-hidden">
        {/* Tab 1: CAD Dispatch Operations Command Center */}
        {activeTab === 'CAD' && (
          <div className="h-full grid grid-cols-1 md:grid-cols-12 gap-3 p-3 min-h-0 overflow-hidden">
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
                onSelectUnit={(unit) => {
                  // Focus unit
                }}
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
          <div className="h-full overflow-y-auto">
            <PublicPortal />
          </div>
        )}

        {/* Tab 3: Command Center Operations & Intelligence Analytics */}
        {activeTab === 'ANALYTICS' && (
          <div className="h-full overflow-y-auto">
            <AnalyticsDashboard
              incidents={incidents}
              units={units}
            />
          </div>
        )}

        {/* Tab 4: Audit Ledger & Fleet MDT Unit Status Controls */}
        {activeTab === 'AUDIT' && (
          <div className="h-full overflow-y-auto">
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
