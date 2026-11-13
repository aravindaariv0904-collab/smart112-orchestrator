import { EmergencyUnit, Incident } from '../types';
import { api } from './api';

export interface UnitMovementState {
  unitId: string;
  callsign: string;
  unitType: string;
  status: string;
  currentLat: number;
  currentLng: number;
  startLat: number;
  startLng: number;
  targetLat: number;
  targetLng: number;
  headingDegrees: number;
  speedKmh: number;
  distanceKm: number;
  estimatedSecondsRemaining: number;
  progress: number; // 0.0 to 1.0
  isMoving: boolean;
  hasArrived: boolean;
  incidentId: string;
  incidentNumber: string;
}

type MovementListener = (states: Record<string, UnitMovementState>) => void;

function toRad(val: number): number {
  return (val * Math.PI) / 180;
}

export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371; // Earth radius in km
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

export function calculateBearing(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const phi1 = toRad(lat1);
  const phi2 = toRad(lat2);
  const deltaLambda = toRad(lon2 - lon1);

  const y = Math.sin(deltaLambda) * Math.cos(phi2);
  const x = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(deltaLambda);
  const theta = Math.atan2(y, x);
  return (Math.round((theta * 180) / Math.PI) + 360) % 360;
}

class TelemetryMovementManager {
  private activeMovements: Record<string, UnitMovementState> = {};
  private listeners: Set<MovementListener> = new Set();
  private timer: any = null;
  private isTicking: boolean = false;

  constructor() {
    this.startTicker();
  }

  private startTicker() {
    if (this.isTicking) return;
    this.isTicking = true;
    this.timer = setInterval(() => this.tick(), 1000);
  }

  public subscribe(listener: MovementListener): () => void {
    this.listeners.add(listener);
    listener({ ...this.activeMovements });
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify() {
    const snapshot = { ...this.activeMovements };
    this.listeners.forEach((fn) => fn(snapshot));
  }

  /**
   * Sync active incidents and units from the polling loop.
   * Finds any assigned unit in DISPATCHED state and initiates or updates movement towards incident.
   */
  public syncState(incidents: Incident[], units: EmergencyUnit[]) {
    const dispatchedIncidents = incidents.filter(
      (inc) => (inc.status === 'DISPATCHED' || inc.status === 'RECOMMENDED') && inc.assigned_unit_id
    );

    const activeUnitIds = new Set<string>();

    for (const inc of dispatchedIncidents) {
      const unit = units.find((u) => u.id === inc.assigned_unit_id);
      if (!unit) continue;

      activeUnitIds.add(unit.id);

      if (!this.activeMovements[unit.id]) {
        // Initialize movement from unit's base coordinates to incident coordinates
        const dist = haversineKm(unit.latitude, unit.longitude, inc.latitude, inc.longitude);
        const bearing = calculateBearing(unit.latitude, unit.longitude, inc.latitude, inc.longitude);
        const speed = 48.0; // km/h emergency priority speed
        const seconds = Math.max(10, Math.round((dist / speed) * 3600));

        this.activeMovements[unit.id] = {
          unitId: unit.id,
          callsign: unit.callsign,
          unitType: unit.unit_type,
          status: unit.status,
          currentLat: unit.latitude,
          currentLng: unit.longitude,
          startLat: unit.latitude,
          startLng: unit.longitude,
          targetLat: inc.latitude,
          targetLng: inc.longitude,
          headingDegrees: bearing,
          speedKmh: speed,
          distanceKm: dist,
          estimatedSecondsRemaining: seconds,
          progress: 0.0,
          isMoving: true,
          hasArrived: false,
          incidentId: inc.id,
          incidentNumber: inc.incident_number,
        };
      } else {
        // Update targets if incident shifted
        const current = this.activeMovements[unit.id];
        current.targetLat = inc.latitude;
        current.targetLng = inc.longitude;
        current.status = unit.status;
      }
    }

    // Clean up units that are no longer dispatched
    for (const unitId of Object.keys(this.activeMovements)) {
      if (!activeUnitIds.has(unitId)) {
        const u = units.find((x) => x.id === unitId);
        if (!u || u.status === 'AVAILABLE') {
          delete this.activeMovements[unitId];
        }
      }
    }

    this.notify();
  }

  /**
   * Internal simulation step executed every 1 second.
   * Advances each dispatched vehicle along the corridor towards the incident scene.
   */
  private async tick() {
    let changed = false;

    for (const [unitId, state] of Object.entries(this.activeMovements)) {
      if (!state.isMoving || state.hasArrived) continue;

      // Advance progress: ~0.035 progress per second = ~28 seconds full travel from base to scene
      const step = 0.035;
      const nextProgress = Math.min(1.0, state.progress + step);
      state.progress = nextProgress;

      // Realistic street-corridor sine curve to simulate following road network
      const jitterLat = 0.0003 * Math.sin(nextProgress * Math.PI * 4);
      const jitterLng = 0.0003 * Math.cos(nextProgress * Math.PI * 4);

      const lat = state.startLat + nextProgress * (state.targetLat - state.startLat) + jitterLat;
      const lng = state.startLng + nextProgress * (state.targetLng - state.startLng) + jitterLng;

      state.currentLat = lat;
      state.currentLng = lng;

      // Update remaining distance and ETA
      const remainingDist = haversineKm(lat, lng, state.targetLat, state.targetLng);
      state.distanceKm = Math.max(0.01, remainingDist);
      state.headingDegrees = calculateBearing(lat, lng, state.targetLat, state.targetLng);
      state.estimatedSecondsRemaining = Math.max(0, Math.round((remainingDist / state.speedKmh) * 3600));

      // Check arrival condition: within 45 meters (0.045 km) or progress == 1.0
      if (nextProgress >= 0.98 || remainingDist <= 0.045) {
        state.progress = 1.0;
        state.currentLat = state.targetLat;
        state.currentLng = state.targetLng;
        state.distanceKm = 0.0;
        state.estimatedSecondsRemaining = 0;
        state.speedKmh = 0.0;
        state.isMoving = false;
        state.hasArrived = true;
        state.status = 'ON_SCENE';

        // Notify backend that unit has arrived on scene
        try {
          await api.updateUnitStatus(
            state.unitId,
            'ON_SCENE',
            state.callsign,
            `Automated Telemetry GPS Gate: Unit arrived at ${state.incidentNumber} incident area.`
          );
        } catch (err) {
          console.warn('Failed to auto-update unit to ON_SCENE:', err);
        }
      }

      changed = true;
    }

    if (changed) {
      this.notify();
    }
  }

  public getMovement(unitId: string): UnitMovementState | undefined {
    return this.activeMovements[unitId];
  }

  public getAllMovements(): Record<string, UnitMovementState> {
    return { ...this.activeMovements };
  }

  public startMovement(
    unit: EmergencyUnit,
    targetLat: number,
    targetLng: number,
    incidentId: string,
    incidentNumber: string
  ): UnitMovementState {
    const dist = haversineKm(unit.latitude, unit.longitude, targetLat, targetLng);
    const bearing = calculateBearing(unit.latitude, unit.longitude, targetLat, targetLng);
    const speed = 52.0;
    const seconds = Math.max(10, Math.round((dist / speed) * 3600));

    const state: UnitMovementState = {
      unitId: unit.id,
      callsign: unit.callsign,
      unitType: unit.unit_type,
      status: 'DISPATCHED',
      currentLat: unit.latitude,
      currentLng: unit.longitude,
      startLat: unit.latitude,
      startLng: unit.longitude,
      targetLat,
      targetLng,
      headingDegrees: bearing,
      speedKmh: speed,
      distanceKm: dist,
      estimatedSecondsRemaining: seconds,
      progress: 0.0,
      isMoving: true,
      hasArrived: false,
      incidentId,
      incidentNumber,
    };

    this.activeMovements[unit.id] = state;
    this.notify();
    return state;
  }

  public resetMovement(unitId: string) {
    delete this.activeMovements[unitId];
    this.notify();
  }
}

export const telemetryMovementManager = new TelemetryMovementManager();
