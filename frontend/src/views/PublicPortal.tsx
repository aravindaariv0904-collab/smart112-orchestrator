import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, 
  Mic, 
  MapPin, 
  CheckCircle, 
  AlertCircle, 
  ShieldAlert, 
  HeartPulse, 
  Flame, 
  Car, 
  Shield, 
  AlertTriangle,
  Clock,
  Navigation,
  RefreshCw,
  Truck,
  Activity,
  History,
  Info,
  ChevronRight,
  PhoneCall,
  CheckCircle2
} from 'lucide-react';
import L from 'leaflet';
import { LeafletMap } from '../map/LeafletMap';
import { citizenStore, CitizenReportRecord } from '../services/citizenStore';
import { telemetryMovementManager, UnitMovementState, haversineKm } from '../services/telemetryService';
import { api } from '../services/api';
import { EmergencyUnit, Incident } from '../types';

const PRESETS = [
  {
    id: 'accident',
    icon: Car,
    title: 'Traffic Collision',
    telugu: 'రోడ్డు ప్రమాదం',
    text: 'Severe multi-vehicle collision near Guntur RTC bus station with trapped passengers and potential fuel leak',
    color: 'border-rose-500/50 bg-rose-950/30 text-rose-300'
  },
  {
    id: 'cardiac',
    icon: HeartPulse,
    title: 'Cardiac Arrest',
    telugu: 'గుండెపోటు అత్యవసరం',
    text: 'Elderly individual collapsed, unresponsive and struggling to breathe, immediate CPR and ambulance needed',
    color: 'border-red-500/50 bg-red-950/30 text-red-300'
  },
  {
    id: 'fire',
    icon: Flame,
    title: 'Fire / Explosion',
    telugu: 'అగ్నిప్రమాదం',
    text: 'Commercial building ground floor fire with dense black smoke spreading rapidly, residents evacuating',
    color: 'border-orange-500/50 bg-orange-950/30 text-orange-300'
  },
  {
    id: 'assault',
    icon: ShieldAlert,
    title: 'Assault / Crime',
    telugu: 'దాడులు / నేరం',
    text: 'Armed robbery and physical altercation in progress, aggressive individuals carrying weapons',
    color: 'border-amber-500/50 bg-amber-950/30 text-amber-300'
  },
  {
    id: 'womens_sos',
    icon: Shield,
    title: "Women's Safety SOS",
    telugu: 'మహిళా రక్షణ అత్యవసరం',
    text: 'Immediate assistance required, caller is being stalked and feels in extreme danger, police unit needed',
    color: 'border-purple-500/50 bg-purple-950/30 text-purple-300'
  }
];

const EMERGENCY_GUIDANCE: Record<string, { en: string[]; te: string[] }> = {
  MEDICAL: {
    en: [
      'Do not move the victim if neck or spinal injury is suspected.',
      'Check for responsiveness and clear the airway; begin CPR if breathing ceases.',
      'Keep patient calm, loosen tight clothing around chest, and keep airway open.'
    ],
    te: [
      'మెడ లేదా వెన్నెముక గాయం అనుమానం ఉంటే బాధితుడిని కదల్చకండి.',
      'శ్వాస సరిగ్గా ఆడుతుందో లేదో చూడండి; అవసరమైతే CPR ప్రారంభించండి.',
      'బాధితుడిని ప్రశాంతంగా ఉంచండి, బిగుతుగా ఉన్న దుస్తులను సడలించండి.'
    ]
  },
  FIRE: {
    en: [
      'Evacuate immediately using emergency stairwells — never use elevators.',
      'Stay low under smoke layer where breathable air remains coolest.',
      'Close doors behind you to compartmentalize and starve flames.'
    ],
    te: [
      'లిఫ్ట్‌లు ఉపయోగించకుండా తక్షణమే నిచ్చెనలు/మెట్ల ద్వారా ఖాళీ చేయండి.',
      'పొగ నుండి తప్పించుకోవడానికి నేలకి దగ్గరగా వంగి నడవండి.',
      'మంటలు వ్యాపించకుండా వెనక ఉన్న తలుపులు మూసివేయండి.'
    ]
  },
  POLICE: {
    en: [
      'Move to a well-lit, populated safe zone immediately.',
      'Do not confront aggressors; note physical descriptions and escape directions.',
      'Keep your phone line free so 112 dispatchers can verify your GPS ping.'
    ],
    te: [
      'వెంటనే కాంతివంతమైన, జనాలు ఉన్న సురక్షిత ప్రాంతానికి వెళ్ళండి.',
      'నిందితులను ఎదుర్కొనే ప్రయత్నం చేయవద్దు; వారి రూపురేఖలను గమనించండి.',
      '112 అధికారులు సంప్రదించడానికి మీ ఫోన్ అందుబాటులో ఉంచండి.'
    ]
  }
};

export const PublicPortal: React.FC = () => {
  const [description, setDescription] = useState<string>('');
  const [address, setAddress] = useState<string>('Guntur RTC Bus Station Complex, AP');
  const [coordinates, setCoordinates] = useState<[number, number]>([16.3067, 80.4365]);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [language, setLanguage] = useState<'EN' | 'TE'>('EN');

  // Citizen's durable case records loaded from localStorage
  const [reports, setReports] = useState<CitizenReportRecord[]>([]);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [activeIncidentData, setActiveIncidentData] = useState<Incident | null>(null);
  const [units, setUnits] = useState<EmergencyUnit[]>([]);
  const [movements, setMovements] = useState<Record<string, UnitMovementState>>({});
  const [showResolvedTab, setShowResolvedTab] = useState<boolean>(false);

  // Dedicated Leaflet tracking map ref
  const trackingMapContainerRef = useRef<HTMLDivElement>(null);
  const trackingMapInstanceRef = useRef<L.Map | null>(null);
  const trackingLayerRef = useRef<L.LayerGroup | null>(null);

  // 1. Initial load of citizen reports from durable localStorage
  useEffect(() => {
    const stored = citizenStore.getReports();
    setReports(stored);
    if (stored.length > 0) {
      // Pick first active report, or first report
      const firstActive = stored.find(r => r.status !== 'RESOLVED');
      setSelectedReportId(firstActive ? firstActive.id : stored[0].id);
    }
  }, []);

  // 2. Fetch fleet units for telemetry coordination
  useEffect(() => {
    const fetchFleet = async () => {
      try {
        const u = await api.getUnits();
        setUnits(u);
      } catch (err) {
        console.warn('Failed to load fleet units:', err);
      }
    };
    fetchFleet();
    const timer = setInterval(fetchFleet, 5000);
    return () => clearInterval(timer);
  }, []);

  // 3. Subscribe to real-time telemetry movement manager
  useEffect(() => {
    const unsub = telemetryMovementManager.subscribe((active) => {
      setMovements(active);
    });
    return unsub;
  }, []);

  // 4. Live polling for the selected citizen incident: keeps report status synced until RESOLVED
  useEffect(() => {
    if (!selectedReportId) {
      setActiveIncidentData(null);
      return;
    }

    const syncSelected = async () => {
      try {
        const res = await fetch(`/api/v1/incidents/${selectedReportId}`);
        if (res.ok) {
          const fresh: Incident = await res.json();
          setActiveIncidentData(fresh);
          // Persist fresh status to localStorage
          const updated = citizenStore.updateReportStatus(fresh.id, fresh);
          if (updated) {
            setReports(citizenStore.getReports());
          }
          // Also feed to telemetryMovementManager
          telemetryMovementManager.syncState([fresh], units);
        }
      } catch (err) {
        console.warn('Could not sync report from backend:', err);
      }
    };

    syncSelected();
    const interval = setInterval(syncSelected, 3500);
    return () => clearInterval(interval);
  }, [selectedReportId, units]);

  const handleMapClick = (lat: number, lng: number) => {
    setCoordinates([lat, lng]);
  };

  const handleSimulateVoiceCall = () => {
    setIsRecording(true);
    setTimeout(() => {
      setDescription(
        "Head-on collision near Guntur RTC bus station, two passengers trapped and unconscious, fuel leaking"
      );
      setIsRecording(false);
    }, 600);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim()) {
      setErrorMsg('Please describe the emergency incident.');
      return;
    }
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const response = await fetch('/api/v1/incidents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description,
          latitude: coordinates[0],
          longitude: coordinates[1],
          address
        })
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to submit report');
      }

      const freshIncident: Incident = await response.json();
      
      // Save durably into citizenStore (localStorage)
      const savedRecord = citizenStore.saveReport(freshIncident);
      const updatedReports = citizenStore.getReports();
      setReports(updatedReports);
      setSelectedReportId(savedRecord.id);
      setActiveIncidentData(freshIncident);
      setDescription('');
    } catch (err: any) {
      setErrorMsg(err.message || 'Submission failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDismissReport = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Dismiss and remove this report from your device history?')) {
      citizenStore.deleteReport(id);
      const remaining = citizenStore.getReports();
      setReports(remaining);
      if (selectedReportId === id) {
        setSelectedReportId(remaining.length > 0 ? remaining[0].id : null);
      }
    }
  };

  const activeReports = reports.filter(r => r.status !== 'RESOLVED');
  const resolvedReports = reports.filter(r => r.status === 'RESOLVED');
  const selectedReport = reports.find(r => r.id === selectedReportId) || null;

  // Find assigned unit & movement for the active report
  const assignedUnitId = activeIncidentData?.assigned_unit_id || selectedReport?.assigned_unit_id;
  const assignedUnit = units.find(u => u.id === assignedUnitId);
  const activeMovement = assignedUnit ? movements[assignedUnit.id] : undefined;

  // Initialize or update Leaflet Tracking Radar map when an incident is selected
  useEffect(() => {
    if (!selectedReport || !trackingMapContainerRef.current) return;

    if (!trackingMapInstanceRef.current) {
      const map = L.map(trackingMapContainerRef.current, {
        center: [selectedReport.latitude, selectedReport.longitude],
        zoom: 13,
        zoomControl: true
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19
      }).addTo(map);

      trackingLayerRef.current = L.layerGroup().addTo(map);
      trackingMapInstanceRef.current = map;
    }

    const map = trackingMapInstanceRef.current;
    const layer = trackingLayerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();

    // 1. Citizen Incident Pin
    const incidentPin = L.divIcon({
      className: 'citizen-incident-marker',
      html: `
        <div class="relative flex items-center justify-center">
          <div class="w-8 h-8 rounded-full bg-rose-600 text-white flex items-center justify-center border-2 border-white shadow-xl animate-bounce">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
            </svg>
          </div>
          <span class="absolute -top-6 whitespace-nowrap bg-rose-950/90 text-[10px] text-rose-200 px-2 py-0.5 rounded border border-rose-500 font-mono font-bold shadow">
            YOUR EMERGENCY LOCATION
          </span>
        </div>
      `,
      iconSize: [32, 32],
      iconAnchor: [16, 16]
    });

    L.marker([selectedReport.latitude, selectedReport.longitude], { icon: incidentPin })
      .bindPopup(`<b>Your Emergency Scene</b><br/>${selectedReport.incident_number}<br/>${selectedReport.address}`)
      .addTo(layer);

    // 2. Assigned Unit Marker with Live Movement Telemetry
    if (assignedUnit) {
      const uLat = activeMovement ? activeMovement.currentLat : assignedUnit.latitude;
      const uLng = activeMovement ? activeMovement.currentLng : assignedUnit.longitude;
      const dist = activeMovement ? activeMovement.distanceKm : haversineKm(uLat, uLng, selectedReport.latitude, selectedReport.longitude);

      let unitIconHtml = `
        <div class="relative flex items-center justify-center">
          <span class="absolute -top-7 whitespace-nowrap bg-emerald-950/90 text-[10px] text-emerald-300 px-2 py-0.5 rounded border border-emerald-500 font-mono font-bold shadow animate-pulse">
            🚑 ${assignedUnit.callsign} (${dist.toFixed(2)} km)
          </span>
          <div class="w-9 h-9 rounded-xl bg-emerald-600 text-white flex items-center justify-center border-2 border-emerald-300 shadow-2xl text-lg hover:scale-110 transition-transform">
            🚑
          </div>
        </div>
      `;

      if (selectedReport.status === 'ON_SCENE' || (activeMovement && activeMovement.hasArrived)) {
        unitIconHtml = `
          <div class="relative flex items-center justify-center">
            <span class="absolute -top-7 whitespace-nowrap bg-purple-950/90 text-[10px] text-purple-200 px-2 py-0.5 rounded border border-purple-500 font-mono font-bold shadow">
              ✓ ON SCENE WITH YOU
            </span>
            <div class="w-10 h-10 rounded-xl bg-purple-600 text-white flex items-center justify-center border-2 border-purple-300 shadow-2xl text-xl ring-4 ring-purple-500/50">
              🚑
            </div>
          </div>
        `;
      }

      const unitMarkerIcon = L.divIcon({
        className: 'citizen-unit-marker',
        html: unitIconHtml,
        iconSize: [36, 36],
        iconAnchor: [18, 18]
      });

      L.marker([uLat, uLng], { icon: unitMarkerIcon })
        .bindPopup(`<b>Assigned Responding Unit</b><br/>${assignedUnit.callsign} (${assignedUnit.unit_type})<br/>Speed: ${activeMovement ? activeMovement.speedKmh.toFixed(0) : '0'} km/h`)
        .addTo(layer);

      // Route line
      L.polyline([
        [uLat, uLng],
        [selectedReport.latitude, selectedReport.longitude]
      ], {
        color: '#10b981',
        weight: 4,
        dashArray: '6, 8',
        opacity: 0.85
      }).addTo(layer);

      // Keep both markers visible
      map.fitBounds([
        [selectedReport.latitude, selectedReport.longitude],
        [uLat, uLng]
      ], { padding: [50, 50], maxZoom: 15 });
    } else {
      map.setView([selectedReport.latitude, selectedReport.longitude], 14);
    }
  }, [selectedReport, assignedUnit, activeMovement]);

  // Clean up tracking map on unmount
  useEffect(() => {
    return () => {
      if (trackingMapInstanceRef.current) {
        trackingMapInstanceRef.current.remove();
        trackingMapInstanceRef.current = null;
      }
    };
  }, []);

  return (
    <div className="h-full p-3 sm:p-5 flex flex-col bg-slate-950 overflow-y-auto">
      {/* Top Banner & Multi-Case Navigation Bar */}
      <div className="mb-4 bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-red-600/20 border border-red-500/40 flex items-center justify-center">
            <ShieldAlert className="w-6 h-6 text-red-500 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-black text-white tracking-tight">112 CITIZEN EMERGENCY PORTAL</h1>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-950 text-rose-300 border border-rose-800 font-bold uppercase">
                Durable Tracking
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Your reported cases are saved continuously on this device until fully resolved.
            </p>
          </div>
        </div>

        {/* Case Switcher Pills & Actions */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => {
              setSelectedReportId(null);
              setShowResolvedTab(false);
            }}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              selectedReportId === null && !showResolvedTab
                ? 'bg-rose-600 text-white shadow-md shadow-rose-900/40'
                : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            }`}
          >
            <Send className="w-3.5 h-3.5" />
            <span>+ Report New Emergency</span>
          </button>

          {activeReports.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => {
                setSelectedReportId(r.id);
                setShowResolvedTab(false);
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-2 ${
                selectedReportId === r.id && !showResolvedTab
                  ? 'bg-sky-600 text-white shadow-md shadow-sky-900/40'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              <span>{r.incident_number}</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-black/30 uppercase font-mono">
                {r.status}
              </span>
            </button>
          ))}

          {resolvedReports.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setShowResolvedTab(true);
                setSelectedReportId(resolvedReports[0].id);
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
                showResolvedTab
                  ? 'bg-purple-600 text-white shadow-md shadow-purple-900/40'
                  : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}
            >
              <History className="w-3.5 h-3.5" />
              <span>Resolved ({resolvedReports.length})</span>
            </button>
          )}

          {/* Telugu / English Toggle */}
          <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs font-bold ml-2">
            <button
              type="button"
              onClick={() => setLanguage('EN')}
              className={`px-2.5 py-1 rounded-lg transition ${language === 'EN' ? 'bg-red-600 text-white' : 'text-slate-400'}`}
            >
              EN
            </button>
            <button
              type="button"
              onClick={() => setLanguage('TE')}
              className={`px-2.5 py-1 rounded-lg transition ${language === 'TE' ? 'bg-red-600 text-white' : 'text-slate-400'}`}
            >
              తెలుగు
            </button>
          </div>
        </div>
      </div>

      {/* Main Dual-Column Content */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-5 min-h-0">
        {/* Left Column: Form OR Active Case Ticket */}
        <div className="lg:col-span-6 bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col justify-between overflow-y-auto">
          {selectedReport ? (
            /* Active / Tracked Case Detail Card */
            <div className="space-y-4">
              {/* Header Status Bar */}
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2.5">
                  <span className={`w-3 h-3 rounded-full ${
                    selectedReport.status === 'RESOLVED'
                      ? 'bg-slate-500'
                      : selectedReport.status === 'ON_SCENE'
                      ? 'bg-purple-500 animate-pulse'
                      : 'bg-emerald-500 animate-ping'
                  }`} />
                  <div>
                    <h2 className="text-sm font-black text-white flex items-center gap-2">
                      <span>Case Tracking:</span>
                      <span className="font-mono text-rose-400">{selectedReport.incident_number}</span>
                    </h2>
                    <p className="text-[11px] text-slate-400">
                      Reported: {new Date(selectedReport.created_at).toLocaleTimeString()} · Persisting in local store
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className={`px-2.5 py-1 rounded-lg text-xs font-bold uppercase tracking-wider ${
                    selectedReport.status === 'RESOLVED'
                      ? 'bg-slate-800 text-slate-300 border border-slate-700'
                      : selectedReport.status === 'ON_SCENE'
                      ? 'bg-purple-950 text-purple-300 border border-purple-800 animate-pulse'
                      : selectedReport.status === 'DISPATCHED'
                      ? 'bg-amber-950 text-amber-300 border border-amber-800'
                      : 'bg-rose-950 text-rose-300 border border-rose-800'
                  }`}>
                    {selectedReport.status}
                  </span>
                  {selectedReport.status === 'RESOLVED' && (
                    <button
                      onClick={(e) => handleDismissReport(selectedReport.id, e)}
                      className="text-[11px] text-slate-500 hover:text-rose-400 underline font-semibold ml-2"
                    >
                      Clear
                    </button>
                  )}
                </div>
              </div>

              {/* Status Stepper Progression */}
              <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-3">
                <span className="text-xs font-bold uppercase text-slate-400 tracking-wider block">
                  {language === 'EN' ? 'Dispatch State Machine' : 'ప్రతిస్పందన పురోగతి'}
                </span>

                <div className="grid grid-cols-4 gap-2 text-center">
                  {/* Step 1: REPORTED */}
                  <div className={`p-2 rounded-lg border text-xs flex flex-col items-center gap-1 ${
                    ['REPORTED', 'ASSESSED', 'RECOMMENDED', 'DISPATCHED', 'ON_SCENE', 'RESOLVED'].includes(selectedReport.status)
                      ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
                      : 'bg-slate-900 border-slate-800 text-slate-500'
                  }`}>
                    <CheckCircle className="w-4 h-4 text-emerald-400" />
                    <span className="font-bold text-[11px]">1. Reported</span>
                    <span className="text-[9px] text-slate-400">Triaged</span>
                  </div>

                  {/* Step 2: ASSESSED */}
                  <div className={`p-2 rounded-lg border text-xs flex flex-col items-center gap-1 ${
                    ['ASSESSED', 'RECOMMENDED', 'DISPATCHED', 'ON_SCENE', 'RESOLVED'].includes(selectedReport.status)
                      ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
                      : 'bg-slate-900 border-slate-800 text-slate-500'
                  }`}>
                    <Activity className="w-4 h-4 text-emerald-400" />
                    <span className="font-bold text-[11px]">2. Unit Ranked</span>
                    <span className="text-[9px] text-slate-400">Proximity</span>
                  </div>

                  {/* Step 3: DISPATCHED */}
                  <div className={`p-2 rounded-lg border text-xs flex flex-col items-center gap-1 ${
                    ['DISPATCHED', 'ON_SCENE', 'RESOLVED'].includes(selectedReport.status)
                      ? 'bg-amber-950/40 border-amber-500/40 text-amber-300 animate-pulse'
                      : 'bg-slate-900 border-slate-800 text-slate-500'
                  }`}>
                    <Truck className="w-4 h-4 text-amber-400" />
                    <span className="font-bold text-[11px]">3. En Route</span>
                    <span className="text-[9px] text-slate-400">Siren active</span>
                  </div>

                  {/* Step 4: ON SCENE / RESOLVED */}
                  <div className={`p-2 rounded-lg border text-xs flex flex-col items-center gap-1 ${
                    ['ON_SCENE', 'RESOLVED'].includes(selectedReport.status)
                      ? 'bg-purple-950/40 border-purple-500/40 text-purple-300'
                      : 'bg-slate-900 border-slate-800 text-slate-500'
                  }`}>
                    <CheckCircle2 className="w-4 h-4 text-purple-400" />
                    <span className="font-bold text-[11px]">4. On Scene</span>
                    <span className="text-[9px] text-slate-400">Mitigation</span>
                  </div>
                </div>
              </div>

              {/* Dynamic Live Ambulance ETA & Distance Banner */}
              {assignedUnit && (
                <div className={`p-4 rounded-xl border flex items-center justify-between shadow-xl ${
                  selectedReport.status === 'ON_SCENE' || (activeMovement && activeMovement.hasArrived)
                    ? 'bg-purple-950/40 border-purple-600/50 text-purple-200'
                    : 'bg-gradient-to-r from-emerald-950/40 to-slate-900 border-emerald-500/40 text-emerald-200'
                }`}>
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-emerald-600/30 border border-emerald-400/50 flex items-center justify-center text-2xl">
                      🚑
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-sm text-white">
                          {assignedUnit.callsign}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-900/60 border border-emerald-600 font-bold uppercase">
                          {assignedUnit.unit_type}
                        </span>
                      </div>
                      <p className="text-xs text-slate-300">
                        {selectedReport.status === 'ON_SCENE' || (activeMovement && activeMovement.hasArrived)
                          ? '🚨 UNIT IS ON SCENE AT YOUR LOCATION'
                          : `En route from ${assignedUnit.station || 'Base'}`}
                      </p>
                    </div>
                  </div>

                  <div className="text-right">
                    {selectedReport.status === 'ON_SCENE' || (activeMovement && activeMovement.hasArrived) ? (
                      <span className="text-xs font-bold text-purple-300 bg-purple-900/60 px-3 py-1 rounded-lg border border-purple-500">
                        ARRIVED
                      </span>
                    ) : (
                      <div>
                        <div className="text-lg font-black text-emerald-400 font-mono">
                          {activeMovement ? `${activeMovement.distanceKm.toFixed(2)} km` : 'Approaching'}
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono">
                          ETA: {activeMovement && activeMovement.estimatedSecondsRemaining > 0
                            ? `~${Math.ceil(activeMovement.estimatedSecondsRemaining / 60)} min`
                            : 'En route'}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Narrative & Location Information */}
              <div className="space-y-2 text-xs bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                <div className="flex items-start justify-between">
                  <span className="text-slate-400 font-bold uppercase text-[10px]">Caller Description:</span>
                  <span className="font-mono text-[10px] text-amber-300">{selectedReport.category}</span>
                </div>
                <p className="text-slate-200 font-sans italic">"{selectedReport.description}"</p>
                <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
                  <span className="flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5 text-rose-400" />
                    <span>{selectedReport.address}</span>
                  </span>
                  <span className="font-mono text-slate-500">
                    {selectedReport.latitude.toFixed(4)}, {selectedReport.longitude.toFixed(4)}
                  </span>
                </div>
              </div>

              {/* Immediate First Aid / Citizen Safety Guidance */}
              <div className="p-3.5 bg-slate-950/80 border border-slate-800 rounded-xl space-y-2">
                <span className="text-xs font-bold uppercase text-amber-400 flex items-center gap-1.5">
                  <Info className="w-4 h-4 text-amber-400" />
                  <span>
                    {language === 'EN' ? 'Safety Instructions While Responders Approach' : 'అత్యవసర సూచనలు'}
                  </span>
                </span>
                <ul className="text-xs text-slate-300 space-y-1.5 list-disc list-inside">
                  {selectedReport.category === 'FIRE'
                    ? (language === 'EN' ? EMERGENCY_GUIDANCE.FIRE.en : EMERGENCY_GUIDANCE.FIRE.te).map((tip, i) => (
                        <li key={i}>{tip}</li>
                      ))
                    : selectedReport.category === 'CRIME' || selectedReport.category === 'WOMENS_SAFETY'
                    ? (language === 'EN' ? EMERGENCY_GUIDANCE.POLICE.en : EMERGENCY_GUIDANCE.POLICE.te).map((tip, i) => (
                        <li key={i}>{tip}</li>
                      ))
                    : (language === 'EN' ? EMERGENCY_GUIDANCE.MEDICAL.en : EMERGENCY_GUIDANCE.MEDICAL.te).map((tip, i) => (
                        <li key={i}>{tip}</li>
                      ))}
                </ul>
              </div>

              {/* Action Buttons */}
              <div className="pt-2 flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setSelectedReportId(null);
                    setDescription('');
                  }}
                  className="flex-1 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold transition flex items-center justify-center gap-1.5"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>{language === 'EN' ? 'Report Another Emergency' : 'మరో అత్యవసరం నివేదించండి'}</span>
                </button>
              </div>
            </div>
          ) : (
            /* Emergency Intake Form */
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <h2 className="text-sm font-bold text-white uppercase tracking-wider mb-2">
                  {language === 'EN' ? '1-Click Fast Emergency Presets' : 'తక్షణ అత్యవసర ఎంపికలు'}
                </h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {PRESETS.map((preset) => {
                    const Icon = preset.icon;
                    return (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => setDescription(preset.text)}
                        className={`p-2.5 rounded-xl border text-left flex flex-col justify-between transition hover:scale-[1.02] cursor-pointer ${preset.color}`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-bold text-xs">{language === 'EN' ? preset.title : preset.telugu}</span>
                          <Icon className="w-4 h-4" />
                        </div>
                        <span className="text-[10px] opacity-80 line-clamp-1">{preset.text}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Demo Voice Simulated Ingestion */}
              <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-white block">
                    {language === 'EN' ? 'Demo Voice Intake (simulated)' : 'వాయిస్ కాల్ అనుకరణ'}
                  </span>
                  <span className="text-[11px] text-slate-400">
                    Fills a sample transcript — no microphone or speech recognition
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleSimulateVoiceCall}
                  disabled={isRecording}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-xs font-bold border transition ${
                    isRecording
                      ? 'bg-red-500 text-white animate-pulse border-red-400'
                      : 'bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-700 cursor-pointer'
                  }`}
                >
                  <Mic className="w-4 h-4" />
                  <span>{isRecording ? 'Filling sample...' : 'Fill Sample'}</span>
                </button>
              </div>

              {/* Text Description */}
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  {language === 'EN' ? 'Emergency Incident Narrative *' : 'అత్యవసర వివరాలు *'}
                </label>
                <textarea
                  id="public-incident-description"
                  aria-label="Emergency incident narrative"
                  rows={4}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={language === 'EN' ? 'Specify injuries, collision, fire, weapons or trapped victims...' : 'గాయాలు, ప్రమాద వివరాలు ఇక్కడ రాయండి...'}
                  className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-red-500 transition font-mono"
                  required
                />
              </div>

              {/* Location Address */}
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  {language === 'EN' ? 'Street Address / Landmark' : 'చిరునామా / ల్యాండ్‌మార్క్'}
                </label>
                <input
                  type="text"
                  id="public-address"
                  aria-label="Street address or landmark"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-red-500 transition"
                />
              </div>

              {/* Pinned Coordinates Display */}
              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2 text-slate-400">
                  <MapPin className="w-4 h-4 text-amber-400" />
                  <span>Map Coordinates (click map on right to update):</span>
                </div>
                <span className="font-mono font-bold text-amber-300">
                  {coordinates[0].toFixed(4)}, {coordinates[1].toFixed(4)}
                </span>
              </div>

              {errorMsg && (
                <div className="p-3 rounded-xl bg-red-950/50 border border-red-800/80 text-xs text-red-200">
                  {errorMsg}
                </div>
              )}

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3.5 rounded-xl bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white font-black text-sm shadow-xl shadow-red-950 flex items-center justify-center space-x-2 transition cursor-pointer disabled:opacity-50"
              >
                <Send className="w-4 h-4" />
                <span>{isSubmitting ? 'Transmitting to 112 Dispatch...' : 'TRANSMIT 112 EMERGENCY CALL'}</span>
              </button>
            </form>
          )}

          <div className="text-[11px] text-slate-500 border-t border-slate-800 pt-3 mt-4 space-y-1">
            <p>
              Prototype only. All incidents, units, and dispatch actions are simulated and require
              human dispatcher approval. Do not use for real emergencies — call 112.
            </p>
            <p>Incident tickets persist securely in your browser cache until marked resolved.</p>
          </div>
        </div>

        {/* Right Column: Dynamic Live Radar Map OR Location Picker */}
        <div className="lg:col-span-6 h-full flex flex-col min-h-[420px]">
          {selectedReport ? (
            /* Live Moving Ambulance Radar Map for Selected Case */
            <div className="flex-1 flex flex-col bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
                  <span className="text-xs font-bold uppercase tracking-wider text-white">
                    Live Response Radar • Unit Telemetry
                  </span>
                </div>
                {activeMovement && (
                  <span className="text-xs font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800">
                    Speed: {activeMovement.speedKmh.toFixed(0)} km/h • Heading: {activeMovement.headingDegrees}°
                  </span>
                )}
              </div>

              <div className="flex-1 rounded-xl overflow-hidden border border-slate-800 relative">
                <div ref={trackingMapContainerRef} className="w-full h-full min-h-[380px]" />

                {/* On-Scene Arrival HUD Alert */}
                {(selectedReport.status === 'ON_SCENE' || (activeMovement && activeMovement.hasArrived)) && (
                  <div className="absolute top-4 left-4 right-4 bg-purple-950/95 border-2 border-purple-500 rounded-xl p-3 shadow-2xl flex items-center gap-3 z-[1000] animate-in fade-in">
                    <div className="w-10 h-10 rounded-lg bg-purple-600 flex items-center justify-center text-xl text-white">
                      🚑
                    </div>
                    <div>
                      <div className="text-xs font-bold text-white">AMBULANCE ARRIVED ON SCENE</div>
                      <div className="text-[11px] text-purple-200">
                        {assignedUnit?.callsign || 'Emergency unit'} is present at your location. Responders are attending to victims.
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* Location Pin Picker for New Report */
            <div className="flex-1 flex flex-col">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <MapPin className="w-4 h-4 text-red-500" />
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                    Interactive Incident Location Pin (Click Map to Place Pin)
                  </span>
                </div>
                <span className="text-[11px] text-slate-500">Free OpenStreetMap Engine</span>
              </div>
              <div className="flex-1 min-h-[400px]">
                <LeafletMap
                  center={coordinates}
                  selectedCoordinates={coordinates}
                  onMapClick={handleMapClick}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};