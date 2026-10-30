import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMapEvents, useMap } from 'react-leaflet';
import L from 'leaflet';

export interface MapIncident {
  id: string;
  incident_number: string;
  latitude: number;
  longitude: number;
  severity: any;
  category: string;
  description: string;
  status: any;
  requires_human_review?: boolean;
  address?: string;
  assessment_data?: string;
  created_at?: string;
  updated_at?: string;
}

export interface MapUnit {
  id: string;
  callsign: string;
  unit_type: string;
  latitude: number;
  longitude: number;
  status: string;
  station?: string;
}

interface LeafletMapProps {
  incidents?: MapIncident[];
  units?: MapUnit[];
  activeIncident?: MapIncident | null;
  assignedUnit?: MapUnit | null;
  selectedCoordinates?: [number, number] | null;
  onMapClick?: (lat: number, lng: number) => void;
  center?: [number, number];
  zoom?: number;
}

// Custom Marker Icons using Leaflet DivIcon
const incidentIcon = L.divIcon({
  className: 'custom-incident-pin',
  html: `<div class="pulsing-pin"></div>`,
  iconSize: [24, 24],
  iconAnchor: [12, 12]
});

const getUnitIcon = (unitType: string) => {
  let emoji = '🚑';
  let borderColor = '#38bdf8';
  if (unitType === 'FIRE_TRUCK') {
    emoji = '🚒';
    borderColor = '#f97316';
  } else if (unitType === 'POLICE_PATROL') {
    emoji = '🚓';
    borderColor = '#3b82f6';
  }
  return L.divIcon({
    className: 'custom-unit-icon',
    html: `<div class="unit-icon" style="border-color: ${borderColor};">${emoji}</div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16]
  });
};

const selectionIcon = L.divIcon({
  className: 'custom-selection-pin',
  html: `<div style="background: #eab308; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 10px rgba(234, 179, 8, 0.8);"></div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10]
});

// Click Listener Component
function MapClickObserver({ onClick }: { onClick?: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(e) {
      if (onClick) {
        onClick(e.latlng.lat, e.latlng.lng);
      }
    }
  });
  return null;
}

// Recenter helper
function MapRecenter({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center);
  }, [center, map]);
  return null;
}

export const LeafletMap: React.FC<LeafletMapProps> = ({
  incidents = [],
  units = [],
  activeIncident,
  assignedUnit,
  selectedCoordinates,
  onMapClick,
  center = [16.3067, 80.4365],
  zoom = 13
}) => {
  // Compute route polyline if both active incident and assigned unit are present
  const routePolyline: [number, number][] = 
    activeIncident && assignedUnit
      ? [
          [assignedUnit.latitude, assignedUnit.longitude],
          [activeIncident.latitude, activeIncident.longitude]
        ]
      : [];

  return (
    <div className="w-full h-full relative rounded-xl overflow-hidden border border-slate-800 shadow-2xl">
      <MapContainer
        center={center}
        zoom={zoom}
        scrollWheelZoom={true}
        style={{ width: '100%', height: '100%', minHeight: '400px', background: '#0b132b' }}
      >
        <MapRecenter center={center} />
        <MapClickObserver onClick={onMapClick} />

        {/* Free OpenStreetMap Tiles */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          className="dark-map-tiles"
        />

        {/* Route Polyline (Assigned Unit -> Incident) */}
        {routePolyline.length > 0 && (
          <Polyline
            positions={routePolyline}
            pathOptions={{ color: '#ef4444', weight: 4, dashArray: '8, 8', opacity: 0.9 }}
          />
        )}

        {/* Selected Picker Coordinate */}
        {selectedCoordinates && (
          <Marker
            position={selectedCoordinates}
            icon={selectionIcon}
            title="Selected emergency intake point"
            alt="Selected emergency intake point"
          >
            <Popup>
              <div className="text-slate-900 font-bold">Selected Emergency Intake Point</div>
            </Popup>
          </Marker>
        )}

        {/* Active Emergency Incidents */}
        {incidents.map((inc) => (
          <Marker
            key={inc.id}
            position={[inc.latitude, inc.longitude]}
            icon={incidentIcon}
            title={`Incident ${inc.incident_number}`}
            alt={`Incident ${inc.incident_number}`}
          >
            <Popup>
              <div className="p-1 text-slate-900">
                <div className="font-extrabold text-sm text-red-600">{inc.incident_number}</div>
                <div className="font-semibold text-xs uppercase tracking-wider">{inc.category}</div>
                <div className="text-xs text-slate-700 mt-1">{inc.description}</div>
                <div className="mt-2 text-[10px] font-mono bg-slate-100 p-1 rounded inline-block">
                  Severity: {inc.severity} | Status: {inc.status}
                </div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Units on Duty */}
        {units.map((unit) => (
          <Marker
            key={unit.id}
            position={[unit.latitude, unit.longitude]}
            icon={getUnitIcon(unit.unit_type)}
            title={`Unit ${unit.callsign}`}
            alt={`Unit ${unit.callsign}`}
          >
            <Popup>
              <div className="p-1 text-slate-900">
                <div className="font-bold text-sm text-sky-600">{unit.callsign}</div>
                <div className="text-xs text-slate-600 font-medium">{unit.unit_type}</div>
                <div className="text-xs text-slate-500">{unit.station}</div>
                <div className={`mt-2 text-[10px] font-bold px-2 py-0.5 rounded inline-block ${
                  unit.status === 'AVAILABLE' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                }`}>
                  {unit.status}
                </div>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
};
