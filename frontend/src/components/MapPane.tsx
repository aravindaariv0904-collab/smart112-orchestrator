import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { Navigation, Compass, Activity, Volume2, VolumeX, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { Incident, EmergencyUnit } from '../types';

interface MapPaneProps {
  incidents: Incident[];
  units: EmergencyUnit[];
  selectedIncident: Incident | null;
  onSelectIncident: (incident: Incident) => void;
  onSelectUnit?: (unit: EmergencyUnit) => void;
  onSimulateArrival?: (unitId: string) => void;
}

export const MapPane: React.FC<MapPaneProps> = ({
  incidents,
  units,
  selectedIncident,
  onSelectIncident,
  onSelectUnit,
  onSimulateArrival
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const routeLayerRef = useRef<L.Polyline | null>(null);
  const trackingMarkerRef = useRef<L.Marker | null>(null);

  // Live tracking telemetry state
  const [trackingProgress, setTrackingProgress] = useState<number>(0.15);
  const [sirenActive, setSirenActive] = useState<boolean>(true);
  const [soundEnabled, setSoundEnabled] = useState<boolean>(false);
  const [liveSpeed, setLiveSpeed] = useState<number>(56);
  const audioCtxRef = useRef<AudioContext | null>(null);

  // Synthesized emergency audio chime / siren using Web Audio API
  useEffect(() => {
    let oscillator: OscillatorNode | null = null;
    let gainNode: GainNode | null = null;
    let timer: any = null;

    if (soundEnabled && sirenActive) {
      try {
        const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
        const ctx = new AudioCtx();
        audioCtxRef.current = ctx;

        oscillator = ctx.createOscillator();
        gainNode = ctx.createGain();
        gainNode.gain.setValueAtTime(0.04, ctx.currentTime);

        oscillator.type = 'sawtooth';
        oscillator.connect(gainNode);
        gainNode.connect(ctx.destination);
        oscillator.start();

        let high = true;
        timer = setInterval(() => {
          if (oscillator && ctx.state === 'running') {
            oscillator.frequency.setValueAtTime(high ? 960 : 720, ctx.currentTime);
            high = !high;
          }
        }, 400);
      } catch (err) {
        console.warn('Web Audio error:', err);
      }
    } else {
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(() => {});
        audioCtxRef.current = null;
      }
    }

    return () => {
      clearInterval(timer);
      if (oscillator) {
        try { oscillator.stop(); } catch {}
      }
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(() => {});
        audioCtxRef.current = null;
      }
    };
  }, [soundEnabled, sirenActive]);

  // Find dispatched or on-scene unit assigned to the selected incident
  const isIncidentDispatched = selectedIncident && (selectedIncident.status === 'DISPATCHED' || selectedIncident.status === 'ON_SCENE');
  const activeDispatchedUnit = isIncidentDispatched
    ? units.find(u => u.status === 'DISPATCHED' || u.status === 'ON_SCENE') || units[0]
    : null;

  // Animate tracking progression smoothly along route
  useEffect(() => {
    if (!isIncidentDispatched) {
      setTrackingProgress(0.15);
      return;
    }

    const interval = setInterval(() => {
      setTrackingProgress((prev) => {
        if (prev >= 0.98) return 0.98;
        // Advance incrementally
        const next = prev + 0.015;
        // Fluctuate speed realistically between 48 and 64 km/h
        setLiveSpeed(Math.floor(48 + Math.random() * 16));
        return next;
      });
    }, 800);

    return () => clearInterval(interval);
  }, [isIncidentDispatched, selectedIncident?.id]);

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (mapInstanceRef.current) return;

    // Center on Guntur / Vijayawada corridor (16.38, 80.52)
    const map = L.map(mapContainerRef.current, {
      center: [16.38, 80.52],
      zoom: 12,
      zoomControl: true
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | Zero-Cost Infrastructure',
      maxZoom: 19
    }).addTo(map);

    markersLayerRef.current = L.layerGroup().addTo(map);
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update Markers & Animated Route when state updates
  useEffect(() => {
    const map = mapInstanceRef.current;
    const layer = markersLayerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();

    // 1. Render Incident Markers
    incidents.forEach((inc) => {
      const isSelected = selectedIncident?.id === inc.id;
      const isCritical = inc.severity === 'LEVEL_1_CRITICAL';
      const isResolved = inc.status === 'RESOLVED';

      let bgClass = 'bg-amber-500';
      if (isResolved) bgClass = 'bg-slate-500';
      else if (isCritical) bgClass = 'bg-rose-600 ring-4 ring-rose-500/40 radar-ping-critical';
      else if (inc.severity === 'LEVEL_2_HIGH') bgClass = 'bg-orange-500';

      const iconHtml = `
        <div class="relative cursor-pointer group flex items-center justify-center">
          <div class="w-8 h-8 rounded-full ${bgClass} text-white flex items-center justify-center shadow-xl border-2 ${isSelected ? 'border-yellow-300 scale-125' : 'border-white'} transition-transform duration-200">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
            </svg>
          </div>
          <span class="absolute -top-6 whitespace-nowrap bg-slate-900/90 text-[10px] text-white px-1.5 py-0.5 rounded border border-slate-700 shadow font-mono pointer-events-none">
            ${inc.incident_number}
          </span>
        </div>
      `;

      const customIcon = L.divIcon({
        html: iconHtml,
        className: 'custom-incident-marker',
        iconSize: [32, 32],
        iconAnchor: [16, 16]
      });

      const marker = L.marker([inc.latitude, inc.longitude], { icon: customIcon });
      marker.on('click', () => {
        onSelectIncident(inc);
      });

      marker.bindPopup(`
        <div class="p-1 space-y-1">
          <div class="flex items-center justify-between gap-2 border-b border-slate-700 pb-1">
            <span class="font-bold text-xs text-rose-400 font-mono">${inc.incident_number}</span>
            <span class="text-[10px] px-1 rounded bg-slate-800 text-slate-300">${inc.status}</span>
          </div>
          <p class="text-xs text-slate-200 font-medium">${inc.category}</p>
          <p class="text-[11px] text-slate-400 line-clamp-2">${inc.description}</p>
          <div class="text-[10px] text-slate-400 pt-1">
            <strong>Severity:</strong> <span class="${isCritical ? 'text-rose-400 font-bold' : 'text-amber-400'}">${inc.severity}</span>
          </div>
        </div>
      `);

      marker.addTo(layer);
    });

    // 2. Render Units Markers
    units.forEach((unit) => {
      let iconColor = 'bg-emerald-600 border-emerald-300';
      if (unit.status === 'DISPATCHED') iconColor = 'bg-amber-600 border-amber-300';
      if (unit.status === 'ON_SCENE') iconColor = 'bg-purple-600 border-purple-300';

      let symbol = '🚑';
      if (unit.unit_type === 'FIRE_TRUCK') symbol = '🚒';
      if (unit.unit_type === 'POLICE_PATROL') symbol = '🚓';

      const isTrackingThisUnit = activeDispatchedUnit?.id === unit.id && isIncidentDispatched;

      const unitHtml = `
        <div class="relative cursor-pointer group flex items-center justify-center ${isTrackingThisUnit ? 'scale-125' : ''}">
          <div class="w-8 h-8 rounded-lg ${iconColor} text-white flex items-center justify-center shadow-lg border-2 text-base hover:scale-110 transition-transform ${isTrackingThisUnit ? 'siren-active' : ''}">
            <span>${symbol}</span>
          </div>
          <span class="absolute -bottom-5 whitespace-nowrap bg-slate-900/90 text-[9px] text-slate-200 px-1 rounded border border-slate-700 font-mono pointer-events-none">
            ${unit.callsign}
          </span>
        </div>
      `;

      const unitIcon = L.divIcon({
        html: unitHtml,
        className: 'custom-unit-marker',
        iconSize: [32, 32],
        iconAnchor: [16, 16]
      });

      // If unit is actively dispatched, calculate animated interpolated position along the route
      let unitLat = unit.latitude;
      let unitLon = unit.longitude;

      if (isTrackingThisUnit && selectedIncident) {
        unitLat = unit.latitude + (selectedIncident.latitude - unit.latitude) * trackingProgress;
        unitLon = unit.longitude + (selectedIncident.longitude - unit.longitude) * trackingProgress;
      }

      const unitMarker = L.marker([unitLat, unitLon], { icon: unitIcon });
      unitMarker.bindPopup(`
        <div class="p-1 space-y-1">
          <div class="flex items-center justify-between gap-2 border-b border-slate-700 pb-1">
            <span class="font-bold text-xs text-emerald-400 font-mono">${unit.callsign}</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded font-bold ${
              unit.status === 'AVAILABLE' ? 'bg-emerald-900/60 text-emerald-300 border border-emerald-500/40' :
              unit.status === 'DISPATCHED' ? 'bg-amber-900/60 text-amber-300 border border-amber-500/40' :
              'bg-purple-900/60 text-purple-300 border border-purple-500/40'
            }">${unit.status}</span>
          </div>
          <p class="text-xs text-slate-300">${unit.unit_type}</p>
          <p class="text-[11px] text-slate-400">Station: ${unit.station || 'Patrol Beat'}</p>
          ${isTrackingThisUnit ? `
            <div class="text-[10px] bg-rose-950/60 text-rose-300 border border-rose-800 p-1 rounded font-mono">
              EN ROUTE: Speed ${liveSpeed} km/h • Siren Active
            </div>
          ` : ''}
        </div>
      `);

      if (onSelectUnit) {
        unitMarker.on('click', () => onSelectUnit(unit));
      }

      unitMarker.addTo(layer);
    });

    // 3. Render Route Polyline when Dispatched
    if (isIncidentDispatched && activeDispatchedUnit && selectedIncident) {
      // Calculate animated interpolated position
      const currentPos: [number, number] = [
        activeDispatchedUnit.latitude + (selectedIncident.latitude - activeDispatchedUnit.latitude) * trackingProgress,
        activeDispatchedUnit.longitude + (selectedIncident.longitude - activeDispatchedUnit.longitude) * trackingProgress
      ];

      // Draw full projected path
      const fullPath = L.polyline(
        [
          [activeDispatchedUnit.latitude, activeDispatchedUnit.longitude],
          [selectedIncident.latitude, selectedIncident.longitude]
        ],
        {
          color: '#38bdf8',
          weight: 4,
          opacity: 0.4,
          dashArray: '4, 8'
        }
      ).addTo(layer);

      // Draw active traversed path
      const activePath = L.polyline(
        [
          currentPos,
          [selectedIncident.latitude, selectedIncident.longitude]
        ],
        {
          color: '#ef4444',
          weight: 5,
          opacity: 0.95,
          className: 'animated-tracking-route'
        }
      ).addTo(layer);
    }

    // 4. Pan to selected incident or tracking unit
    if (selectedIncident) {
      map.panTo([selectedIncident.latitude, selectedIncident.longitude], {
        animate: true,
        duration: 0.8
      });
    }
  }, [incidents, units, selectedIncident, trackingProgress, liveSpeed, isIncidentDispatched, onSelectIncident, onSelectUnit]);

  // Calculate live remaining distance and ETA
  const remainingDistanceKm = selectedIncident && activeDispatchedUnit
    ? Math.max(0.1, +(Math.sqrt(
        Math.pow((selectedIncident.latitude - (activeDispatchedUnit.latitude + (selectedIncident.latitude - activeDispatchedUnit.latitude) * trackingProgress)) * 111, 2) +
        Math.pow((selectedIncident.longitude - (activeDispatchedUnit.longitude + (selectedIncident.longitude - activeDispatchedUnit.longitude) * trackingProgress)) * 105, 2)
      )).toFixed(2))
    : 1.2;

  const remainingMinutes = Math.max(1, Math.round((remainingDistanceKm / 45) * 60));

  return (
    <div className="relative w-full h-full min-h-[350px] bg-slate-950 rounded-xl overflow-hidden border border-slate-800 shadow-2xl">
      <div ref={mapContainerRef} className="w-full h-full z-0" />

      {/* Floating Active Tracking Telemetry HUD */}
      {isIncidentDispatched && activeDispatchedUnit && selectedIncident && (
        <div className="absolute bottom-4 left-4 right-4 z-[1000] bg-slate-900/95 backdrop-blur-md border border-rose-500/50 rounded-xl p-3 shadow-2xl flex flex-wrap items-center justify-between gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-rose-600/20 border border-rose-500 flex items-center justify-center siren-active">
              <span className="text-xl">
                {activeDispatchedUnit.unit_type === 'AMBULANCE' ? '🚑' : activeDispatchedUnit.unit_type === 'FIRE_TRUCK' ? '🚒' : '🚓'}
              </span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-sm text-white font-mono">{activeDispatchedUnit.callsign}</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-500 text-white font-bold animate-pulse">
                  EN ROUTE (HIGH PRIORITY)
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Tracking vector towards <span className="text-white font-semibold">{selectedIncident.incident_number}</span> ({selectedIncident.category})
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono">
            {/* Speedometer */}
            <div className="bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800 text-center">
              <span className="text-[10px] text-slate-500 uppercase block font-sans">Speed</span>
              <span className="font-bold text-sky-400 text-sm">{liveSpeed} <span className="text-[10px] text-slate-400">km/h</span></span>
            </div>

            {/* Distance Remaining */}
            <div className="bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800 text-center">
              <span className="text-[10px] text-slate-500 uppercase block font-sans">Remaining</span>
              <span className="font-bold text-amber-400 text-sm">{remainingDistanceKm} <span className="text-[10px] text-slate-400">km</span></span>
            </div>

            {/* Live ETA Countdown */}
            <div className="bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800 text-center">
              <span className="text-[10px] text-slate-500 uppercase block font-sans">ETA</span>
              <span className="font-bold text-emerald-400 text-sm">{remainingMinutes} <span className="text-[10px] text-slate-400">min</span></span>
            </div>

            {/* Siren Audio Toggle */}
            <button
              onClick={() => setSoundEnabled(!soundEnabled)}
              className={`p-2 rounded-lg border transition ${
                soundEnabled
                  ? 'bg-rose-600 text-white border-rose-400 animate-pulse'
                  : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
              }`}
              title={soundEnabled ? 'Mute Siren Audio' : 'Play Radio Siren Alert'}
            >
              {soundEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            </button>

            {/* Mark Arrival Quick Action */}
            {onSimulateArrival && (
              <button
                onClick={() => onSimulateArrival(activeDispatchedUnit.id)}
                className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 shadow-lg shadow-emerald-950 transition cursor-pointer"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>Simulate On Scene</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Cartography Legend */}
      <div className="absolute top-3 right-3 z-[1000] bg-slate-900/90 backdrop-blur-md px-3 py-2 rounded-lg border border-slate-800 text-[11px] space-y-1 shadow-lg pointer-events-auto">
        <div className="text-[10px] font-semibold tracking-wider text-slate-400 uppercase pb-1 border-b border-slate-800 flex items-center justify-between gap-2">
          <span>Live Cartography</span>
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
        </div>
        <div className="flex items-center gap-2 text-slate-200">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-600 ring-2 ring-rose-400/40"></span>
          <span>Critical Incident (112)</span>
        </div>
        <div className="flex items-center gap-2 text-slate-200">
          <span className="w-2.5 h-2.5 rounded-full bg-orange-500"></span>
          <span>High Priority Incident</span>
        </div>
        <div className="flex items-center gap-2 text-slate-200">
          <span className="w-2.5 h-2.5 rounded-sm bg-emerald-600"></span>
          <span>Available Emergency Unit</span>
        </div>
        <div className="flex items-center gap-2 text-slate-200">
          <span className="w-2.5 h-2.5 rounded-sm bg-amber-600"></span>
          <span>Dispatched / En Route</span>
        </div>
      </div>
    </div>
  );
};
