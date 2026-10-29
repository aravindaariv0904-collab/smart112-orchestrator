import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { Navigation, Activity, Volume2, VolumeX, ShieldAlert, CheckCircle2, AlertTriangle } from 'lucide-react';
import { Incident, EmergencyUnit } from '../types';

interface MapPaneProps {
  incidents: Incident[];
  units: EmergencyUnit[];
  selectedIncident: Incident | null;
  onSelectIncident: (incident: Incident) => void;
  onSelectUnit?: (unit: EmergencyUnit) => void;
  onSimulateArrival?: (unitId: string) => void;
}

const ACTIVE_STATUSES = ['DISPATCHED', 'ON_SCENE'];

/** Escape untrusted strings before interpolating into Leaflet HTML popups. */
function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** Great-circle distance in km (straight-line only; not a routed ETA). */
function haversineKm(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const toRad = (value: number) => (value * Math.PI) / 180;
  const earthRadiusKm = 6371;
  const dLat = toRad(bLat - aLat);
  const dLon = toRad(bLon - aLon);
  const lat1 = toRad(aLat);
  const lat2 = toRad(bLat);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return earthRadiusKm * 2 * Math.asin(Math.min(1, Math.sqrt(h)));
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

  const [sirenActive] = useState<boolean>(true);
  const [soundEnabled, setSoundEnabled] = useState<boolean>(false);
  const [tileError, setTileError] = useState<boolean>(false);
  const audioCtxRef = useRef<AudioContext | null>(null);

  // Synthesized siren tone is a local UI effect, not real radio audio.
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
    } else if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }

    return () => {
      clearInterval(timer);
      if (oscillator) {
        try {
          oscillator.stop();
        } catch {
          /* already stopped */
        }
      }
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(() => {});
        audioCtxRef.current = null;
      }
    };
  }, [soundEnabled, sirenActive]);

  const isIncidentDispatched =
    selectedIncident && ACTIVE_STATUSES.includes(selectedIncident.status);

  // Prefer the unit the backend actually assigned; never guess an arbitrary busy unit.
  const assignedUnit = isIncidentDispatched
    ? units.find((unit) => unit.id === selectedIncident?.assigned_unit_id) || null
    : null;

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [16.38, 80.52],
      zoom: 12,
      zoomControl: true
    });

    const tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19
    });
    tiles.on('tileerror', () => setTileError(true));
    tiles.on('load', () => setTileError(false));
    tiles.addTo(map);

    markersLayerRef.current = L.layerGroup().addTo(map);
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update markers and route whenever data changes. Positions come from the
  // backend record; there is no client-side position interpolation.
  useEffect(() => {
    const map = mapInstanceRef.current;
    const layer = markersLayerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();

    // 1. Incident markers
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
            ${escapeHtml(inc.incident_number)}
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
      marker.on('click', () => onSelectIncident(inc));

      marker.bindPopup(`
        <div class="p-1 space-y-1">
          <div class="flex items-center justify-between gap-2 border-b border-slate-700 pb-1">
            <span class="font-bold text-xs text-rose-400 font-mono">${escapeHtml(inc.incident_number)}</span>
            <span class="text-[10px] px-1 rounded bg-slate-800 text-slate-300">${escapeHtml(inc.status)}</span>
          </div>
          <p class="text-xs text-slate-200 font-medium">${escapeHtml(inc.category)}</p>
          <p class="text-[11px] text-slate-400 line-clamp-2">${escapeHtml(inc.description)}</p>
          <div class="text-[10px] text-slate-400 pt-1">
            <strong>Severity:</strong> <span class="${isCritical ? 'text-rose-400 font-bold' : 'text-amber-400'}">${escapeHtml(inc.severity)}</span>
          </div>
        </div>
      `);

      marker.addTo(layer);
    });

    // 2. Unit markers (seeded positions from the backend)
    units.forEach((unit) => {
      let iconColor = 'bg-emerald-600 border-emerald-300';
      if (unit.status === 'DISPATCHED') iconColor = 'bg-amber-600 border-amber-300';
      if (unit.status === 'ON_SCENE') iconColor = 'bg-purple-600 border-purple-300';

      let symbol = '🚑';
      if (unit.unit_type === 'FIRE_TRUCK') symbol = '🚒';
      if (unit.unit_type === 'POLICE_PATROL') symbol = '🚓';

      const isTrackingThisUnit = assignedUnit?.id === unit.id;

      const unitHtml = `
        <div class="relative cursor-pointer group flex items-center justify-center ${isTrackingThisUnit ? 'scale-125' : ''}">
          <div class="w-8 h-8 rounded-lg ${iconColor} text-white flex items-center justify-center shadow-lg border-2 text-base hover:scale-110 transition-transform">
            <span>${symbol}</span>
          </div>
          <span class="absolute -bottom-5 whitespace-nowrap bg-slate-900/90 text-[9px] text-slate-200 px-1 rounded border border-slate-700 font-mono pointer-events-none">
            ${escapeHtml(unit.callsign)}
          </span>
        </div>
      `;

      const unitIcon = L.divIcon({
        html: unitHtml,
        className: 'custom-unit-marker',
        iconSize: [32, 32],
        iconAnchor: [16, 16]
      });

      const unitMarker = L.marker([unit.latitude, unit.longitude], { icon: unitIcon });
      unitMarker.bindPopup(`
        <div class="p-1 space-y-1">
          <div class="flex items-center justify-between gap-2 border-b border-slate-700 pb-1">
            <span class="font-bold text-xs text-emerald-400 font-mono">${escapeHtml(unit.callsign)}</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded font-bold ${
              unit.status === 'AVAILABLE'
                ? 'bg-emerald-900/60 text-emerald-300 border border-emerald-500/40'
                : unit.status === 'DISPATCHED'
                ? 'bg-amber-900/60 text-amber-300 border border-amber-500/40'
                : 'bg-purple-900/60 text-purple-300 border border-purple-500/40'
            }">${escapeHtml(unit.status)}</span>
          </div>
          <p class="text-xs text-slate-300">${escapeHtml(unit.unit_type)}</p>
          <p class="text-[11px] text-slate-400">Station: ${escapeHtml(unit.station || 'Not recorded')}</p>
          <p class="text-[10px] text-slate-500 font-mono">Position: ${unit.latitude.toFixed(4)}, ${unit.longitude.toFixed(4)}</p>
        </div>
      `);

      if (onSelectUnit) {
        unitMarker.on('click', () => onSelectUnit(unit));
      }

      unitMarker.addTo(layer);
    });

    // 3. Straight-line route between the assigned unit and the incident
    if (isIncidentDispatched && assignedUnit && selectedIncident) {
      L.polyline(
        [
          [assignedUnit.latitude, assignedUnit.longitude],
          [selectedIncident.latitude, selectedIncident.longitude]
        ],
        {
          color: '#38bdf8',
          weight: 4,
          opacity: 0.7,
          dashArray: '6, 8',
          className: 'animated-tracking-route'
        }
      ).addTo(layer);
    }

    // 4. Pan to the selected incident
    if (selectedIncident) {
      map.panTo([selectedIncident.latitude, selectedIncident.longitude], {
        animate: true,
        duration: 0.8
      });
    }
  }, [
    incidents,
    units,
    selectedIncident,
    isIncidentDispatched,
    assignedUnit,
    onSelectIncident,
    onSelectUnit
  ]);

  const straightLineKm =
    selectedIncident && assignedUnit
      ? haversineKm(
          assignedUnit.latitude,
          assignedUnit.longitude,
          selectedIncident.latitude,
          selectedIncident.longitude
        )
      : null;

  return (
    <div className="relative w-full h-full min-h-[350px] bg-slate-950 rounded-xl overflow-hidden border border-slate-800 shadow-2xl">
      <div ref={mapContainerRef} className="w-full h-full z-0" />

      {/* GIS tile failure banner — incident data stays available elsewhere */}
      {tileError && (
        <div className="absolute top-3 left-3 z-[1000] max-w-xs bg-rose-950/95 border border-rose-700 rounded-lg p-3 text-[11px] text-rose-200 shadow-lg flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-px" />
          <span>
            Map tiles could not be loaded. Incident details remain available in the triage queue
            and detail panel; no ETA is generated.
          </span>
        </div>
      )}

      {/* Assigned-unit HUD — straight-line distance only, no invented ETA */}
      {isIncidentDispatched && assignedUnit && selectedIncident && (
        <div className="absolute bottom-4 left-4 right-4 z-[1000] bg-slate-900/95 border border-amber-500/50 rounded-xl p-3 shadow-2xl flex flex-wrap items-center justify-between gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-600/20 border border-amber-500 flex items-center justify-center">
              <span className="text-xl">
                {assignedUnit.unit_type === 'AMBULANCE'
                  ? '🚑'
                  : assignedUnit.unit_type === 'FIRE_TRUCK'
                  ? '🚒'
                  : '🚓'}
              </span>
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-extrabold text-sm text-white font-mono">
                  {assignedUnit.callsign}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500 text-slate-950 font-bold">
                  {selectedIncident.status}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 font-bold uppercase tracking-wider">
                  Simulated fleet
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Assigned to{' '}
                <span className="text-white font-semibold">
                  {selectedIncident.incident_number}
                </span>{' '}
                ({selectedIncident.category})
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs font-mono">
            <div className="bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800 text-center">
              <span className="text-[10px] text-slate-500 uppercase block font-sans">
                Straight-line
              </span>
              <span className="font-bold text-amber-400 text-sm">
                {straightLineKm !== null ? straightLineKm.toFixed(1) : '—'}{' '}
                <span className="text-[10px] text-slate-400">km</span>
              </span>
            </div>

            <div className="bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800 text-center">
              <span className="text-[10px] text-slate-500 uppercase block font-sans">ETA</span>
              <span className="font-bold text-slate-400 text-sm" title="No routing provider configured">
                N/A
              </span>
            </div>

            <button
              type="button"
              onClick={() => setSoundEnabled((previous) => !previous)}
              className={`p-2 rounded-lg border transition ${
                soundEnabled
                  ? 'bg-rose-600 text-white border-rose-400'
                  : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
              }`}
              title={soundEnabled ? 'Mute local siren tone' : 'Play local siren tone (UI only)'}
              aria-pressed={soundEnabled}
              aria-label={soundEnabled ? 'Mute local siren tone' : 'Play local siren tone'}
            >
              {soundEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            </button>

            {onSimulateArrival && (
              <button
                type="button"
                onClick={() => onSimulateArrival(assignedUnit.id)}
                className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 shadow-lg shadow-emerald-950 transition"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>Mark On Scene</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Cartography Legend */}
      <div className="absolute top-3 right-3 z-[1000] bg-slate-900/95 px-3 py-2 rounded-lg border border-slate-800 text-[11px] space-y-1 shadow-lg pointer-events-auto">
        <div className="text-[10px] font-semibold tracking-wider text-slate-400 uppercase pb-1 border-b border-slate-800 flex items-center gap-2">
          <Activity className="w-3 h-3 text-sky-400" />
          <span>Simulated Fleet Map</span>
        </div>
        <div className="flex items-center gap-2 text-slate-200">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-600 ring-2 ring-rose-400/40"></span>
          <span>Critical incident</span>
        </div>
        <div className="flex items-center gap-2 text-slate-200">
          <span className="w-2.5 h-2.5 rounded-full bg-orange-500"></span>
          <span>High priority incident</span>
        </div>
        <div className="flex items-center gap-2 text-slate-200">
          <span className="w-2.5 h-2.5 rounded-sm bg-emerald-600"></span>
          <span>Available unit</span>
        </div>
        <div className="flex items-center gap-2 text-slate-200">
          <span className="w-2.5 h-2.5 rounded-sm bg-amber-600"></span>
          <span>Dispatched / en route</span>
        </div>
        <div className="flex items-center gap-2 text-slate-500 pt-1 border-t border-slate-800">
          <Navigation className="w-3 h-3" />
          <span>Positions are seeded, not live GPS</span>
        </div>
      </div>
    </div>
  );
};
