import React, { useState, useEffect } from 'react';
import { 
  Building2, 
  Bed, 
  HeartPulse, 
  Activity, 
  ShieldAlert, 
  Clock, 
  PhoneCall, 
  CheckCircle, 
  AlertTriangle, 
  RefreshCw,
  Search,
  ChevronRight,
  Filter,
  Droplets,
  Stethoscope
} from 'lucide-react';
import { Facility } from '../types';
import { api } from '../services/api';

export const FacilitiesDashboard: React.FC = () => {
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [filterType, setFilterType] = useState<string>('ALL');
  const [selectedFacility, setSelectedFacility] = useState<Facility | null>(null);
  const [handoverSuccess, setHandoverSuccess] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadFacilities = async () => {
    setIsLoading(true);
    try {
      const data = await api.getFacilities();
      setFacilities(data);
      if (data.length > 0 && !selectedFacility) {
        setSelectedFacility(data[0]);
      } else if (selectedFacility) {
        const fresh = data.find(f => f.id === selectedFacility.id);
        if (fresh) setSelectedFacility(fresh);
      }
      setErrorMsg(null);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load medical facilities');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadFacilities();
    const interval = setInterval(loadFacilities, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleSimulateHandover = (facility: Facility) => {
    setHandoverSuccess(`Patient handover initiated with ${facility.name} Emergency Intake. Trauma team notified.`);
    setTimeout(() => setHandoverSuccess(null), 4000);
  };

  const filteredFacilities = facilities.filter(f => {
    const fType = f.facility_type || '';
    const matchesSearch = f.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          (f.address && f.address.toLowerCase().includes(searchQuery.toLowerCase())) ||
                          fType.toLowerCase().includes(searchQuery.toLowerCase());
    if (!matchesSearch) return false;
    if (filterType === 'TRAUMA' && !fType.includes('TRAUMA')) return false;
    if (filterType === 'ICU' && !f.has_icu) return false;
    if (filterType === 'EMERGENCY' && !f.has_emergency) return false;
    return true;
  });

  const totalBeds = facilities.reduce((acc, f) => acc + (f.bed_count || 0), 0);
  const totalAvailable = facilities.reduce((acc, f) => acc + (f.available_beds || 0), 0);
  const totalTraumaUnits = facilities.filter(f => (f.facility_type || '').includes('TRAUMA') || f.has_emergency).length;

  return (
    <div className="h-full p-4 lg:p-6 bg-slate-950 flex flex-col overflow-y-auto">
      {/* Top Overview KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider block">Total Network Facilities</span>
            <span className="text-2xl font-black text-white mt-1 block">{facilities.length}</span>
            <span className="text-[11px] text-slate-500">Guntur &amp; Vijayawada Corridor</span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-sky-950 border border-sky-800/60 flex items-center justify-center text-sky-400">
            <Building2 className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider block">Available Beds</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-black text-emerald-400">{totalAvailable}</span>
              <span className="text-xs text-slate-500">/ {totalBeds} Total</span>
            </div>
            <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
              <div 
                className="bg-emerald-500 h-full rounded-full transition-all duration-500" 
                style={{ width: `${totalBeds > 0 ? (totalAvailable / totalBeds) * 100 : 0}%` }}
              />
            </div>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-950 border border-emerald-800/60 flex items-center justify-center text-emerald-400">
            <Bed className="w-6 h-6" />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider block">Active Trauma Hubs</span>
            <span className="text-2xl font-black text-rose-400 mt-1 block">{totalTraumaUnits}</span>
            <span className="text-[11px] text-slate-500">Level 1 &amp; 2 Emergency Resus</span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-rose-950 border border-rose-800/60 flex items-center justify-center text-rose-400">
            <ShieldAlert className="w-6 h-6 animate-pulse" />
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl flex items-center justify-between">
          <div>
            <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider block">Corridor Status</span>
            <span className="text-sm font-black text-emerald-400 mt-1 block uppercase">NORMAL OPERATIONS</span>
            <span className="text-[11px] text-slate-500">Zero Critical Diverts</span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-950 border border-emerald-800/60 flex items-center justify-center text-emerald-400">
            <Activity className="w-6 h-6" />
          </div>
        </div>
      </div>

      {handoverSuccess && (
        <div className="mb-4 p-3 bg-emerald-950/80 border border-emerald-500 rounded-xl text-xs text-emerald-200 flex items-center justify-between animate-in fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-400" />
            <span>{handoverSuccess}</span>
          </div>
        </div>
      )}

      {/* Main Grid: Facility List + Detail & Handover Panel */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-0">
        {/* Left Column: Hospital Directory (7 cols) */}
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col min-h-0">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-800">
            <div>
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <Building2 className="w-4 h-4 text-rose-500" />
                <span>Regional Hospital &amp; Facility Network</span>
              </h2>
              <p className="text-xs text-slate-400">Select a facility to inspect bed capacity, ICU availability, and handovers</p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={loadFacilities}
                disabled={isLoading}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
                title="Refresh facility data"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-rose-400' : ''}`} />
              </button>
            </div>
          </div>

          {/* Search & Filter Toolbar */}
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search hospital name, address, or specialty..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-rose-500 transition"
              />
            </div>

            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs font-semibold">
              {['ALL', 'TRAUMA', 'ICU', 'EMERGENCY'].map((f) => (
                <button
                  key={f}
                  onClick={() => setFilterType(f)}
                  className={`px-2.5 py-1 rounded-lg transition ${
                    filterType === f ? 'bg-rose-600 text-white' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {/* Facility Cards List */}
          <div className="flex-1 space-y-3 overflow-y-auto pr-1">
            {filteredFacilities.map((fac) => {
              const isSelected = selectedFacility?.id === fac.id;
              const bedCount = fac.bed_count || 0;
              const availBeds = fac.available_beds || 0;
              const occRatio = bedCount > 0 ? (availBeds / bedCount) : 0;
              const isLowCapacity = occRatio < 0.15;

              return (
                <div
                  key={fac.id}
                  onClick={() => setSelectedFacility(fac)}
                  className={`p-4 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-slate-800/90 border-rose-500/80 shadow-lg shadow-rose-950/20'
                      : 'bg-slate-950/60 border-slate-800 hover:bg-slate-800/40 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm ${
                        fac.has_emergency ? 'bg-rose-950/80 border border-rose-800/60 text-rose-400' : 'bg-slate-800 text-slate-300'
                      }`}>
                        🏥
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-xs font-bold text-white hover:text-rose-400 transition">
                            {fac.name}
                          </h3>
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 font-mono font-semibold">
                            {fac.facility_type || 'HOSPITAL'}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 mt-0.5">{fac.address || 'Andhra Pradesh'}</p>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className={`text-xs font-bold font-mono px-2 py-0.5 rounded ${
                        isLowCapacity ? 'bg-rose-950 text-rose-300 border border-rose-800' : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                      }`}>
                        {availBeds} / {bedCount} Beds Avail
                      </span>
                    </div>
                  </div>

                  {/* Badges Row */}
                  <div className="mt-3 pt-3 border-t border-slate-800 flex flex-wrap items-center justify-between text-[11px] text-slate-400 gap-2">
                    <div className="flex items-center gap-2">
                      {fac.has_emergency && (
                        <span className="px-2 py-0.5 rounded bg-rose-950/60 text-rose-300 border border-rose-800/50 font-semibold text-[10px]">
                          🚨 Emergency Dept
                        </span>
                      )}
                      {fac.has_icu && (
                        <span className="px-2 py-0.5 rounded bg-sky-950/60 text-sky-300 border border-sky-800/50 font-semibold text-[10px]">
                          🫀 ICU &amp; Trauma
                        </span>
                      )}
                      {fac.phone && (
                        <span className="flex items-center gap-1 font-mono text-[10px] text-slate-400">
                          <PhoneCall className="w-3 h-3 text-emerald-400" />
                          <span>{fac.phone}</span>
                        </span>
                      )}
                    </div>
                    <span className="font-mono text-[10px] text-slate-500">
                      {fac.latitude.toFixed(4)}, {fac.longitude.toFixed(4)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Selected Hospital Detailed Profile & Handover Console (5 cols) */}
        <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col justify-between overflow-y-auto">
          {selectedFacility ? (
            <div className="space-y-5">
              <div className="border-b border-slate-800 pb-4">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold text-rose-400 bg-rose-950/60 px-2 py-0.5 rounded border border-rose-800">
                    FACILITY DETAIL
                  </span>
                  <span className="text-xs font-mono text-emerald-400 font-bold">ACCEPTING INBOUND</span>
                </div>
                <h3 className="text-base font-black text-white mt-2">{selectedFacility.name}</h3>
                <p className="text-xs text-slate-400">{selectedFacility.address}</p>
              </div>

              {/* Bed Capacity Progress Card */}
              {(() => {
                const selBedCount = selectedFacility.bed_count || 0;
                const selAvailBeds = selectedFacility.available_beds || 0;
                return (
                  <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-white flex items-center gap-1.5">
                        <Bed className="w-4 h-4 text-emerald-400" />
                        <span>Bed Allocation Status</span>
                      </span>
                      <span className="text-xs font-mono font-bold text-emerald-400">
                        {((selAvailBeds / (selBedCount || 1)) * 100).toFixed(0)}% Available
                      </span>
                    </div>

                    <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
                      <div
                        className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                        style={{ width: `${(selAvailBeds / (selBedCount || 1)) * 100}%` }}
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-2 text-center text-xs">
                      <div className="p-2 rounded-lg bg-slate-900 border border-slate-800">
                        <span className="text-[10px] text-slate-500 uppercase block font-semibold">Available Beds</span>
                        <span className="text-base font-mono font-bold text-emerald-400">{selAvailBeds}</span>
                      </div>
                      <div className="p-2 rounded-lg bg-slate-900 border border-slate-800">
                        <span className="text-[10px] text-slate-500 uppercase block font-semibold">Total Capacity</span>
                        <span className="text-base font-mono font-bold text-slate-200">{selBedCount}</span>
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* Specializations & Capabilities */}
              <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-3">
                <span className="text-xs font-bold text-white uppercase tracking-wider block">
                  Clinical Capabilities &amp; Infrastructure
                </span>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2 rounded-lg bg-slate-900 border border-slate-800 flex items-center gap-2">
                    <CheckCircle className={`w-4 h-4 ${selectedFacility.has_emergency ? 'text-emerald-400' : 'text-slate-600'}`} />
                    <span className="text-slate-300">24/7 Emergency</span>
                  </div>
                  <div className="p-2 rounded-lg bg-slate-900 border border-slate-800 flex items-center gap-2">
                    <CheckCircle className={`w-4 h-4 ${selectedFacility.has_icu ? 'text-emerald-400' : 'text-slate-600'}`} />
                    <span className="text-slate-300">Intensive Care (ICU)</span>
                  </div>
                  <div className="p-2 rounded-lg bg-slate-900 border border-slate-800 flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-emerald-400" />
                    <span className="text-slate-300">Trauma Resuscitation</span>
                  </div>
                  <div className="p-2 rounded-lg bg-slate-900 border border-slate-800 flex items-center gap-2">
                    <Droplets className="w-4 h-4 text-rose-400" />
                    <span className="text-slate-300">Blood Bank On-Site</span>
                  </div>
                </div>
              </div>

              {/* Patient Handover Action Button */}
              <div className="pt-3 border-t border-slate-800 space-y-2">
                <button
                  type="button"
                  onClick={() => handleSimulateHandover(selectedFacility)}
                  className="w-full py-3 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-black text-xs shadow-lg shadow-emerald-950 flex items-center justify-center gap-2 transition cursor-pointer"
                >
                  <Activity className="w-4 h-4" />
                  <span>PRE-NOTIFY HOSPITAL FOR INCOMING PATIENT</span>
                </button>
                <p className="text-[10px] text-slate-500 text-center">
                  Coordinates ambulance arrival with emergency bay triage team.
                </p>
              </div>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-500 text-xs">
              Select a facility from the network directory to view clinical profile.
            </div>
          )}

          <div className="mt-4 pt-3 border-t border-slate-800 text-[11px] text-slate-500">
            Directly connected to regional Health Information Exchange (HIE).
          </div>
        </div>
      </div>
    </div>
  );
};