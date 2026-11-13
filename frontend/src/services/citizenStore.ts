import { Incident } from '../types';

export interface CitizenReportRecord {
  id: string;
  incident_number: string;
  description: string;
  category: string;
  severity: string;
  status: string;
  latitude: number;
  longitude: number;
  address: string;
  assigned_unit_id?: string | null;
  assigned_unit_callsign?: string | null;
  created_at: string;
  updated_at?: string;
  notes?: string;
}

const STORAGE_KEY = 'smart112_citizen_reports_v1';

export const citizenStore = {
  getReports(): CitizenReportRecord[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      return JSON.parse(raw);
    } catch {
      return [];
    }
  },

  saveReport(incident: Partial<Incident> & { id: string }): CitizenReportRecord {
    const reports = this.getReports();
    const existingIndex = reports.findIndex(r => r.id === incident.id);
    
    const record: CitizenReportRecord = {
      id: incident.id,
      incident_number: incident.incident_number || `INC-${incident.id.slice(0, 8)}`,
      description: incident.description || '',
      category: incident.category || 'EMERGENCY',
      severity: incident.severity || 'LEVEL_2_HIGH',
      status: incident.status || 'REPORTED',
      latitude: incident.latitude || 16.3067,
      longitude: incident.longitude || 80.4365,
      address: incident.address || 'Guntur, Andhra Pradesh',
      assigned_unit_id: incident.assigned_unit_id || null,
      assigned_unit_callsign: (incident as any).assigned_unit_callsign || null,
      created_at: incident.created_at || new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    if (existingIndex >= 0) {
      reports[existingIndex] = { ...reports[existingIndex], ...record };
    } else {
      reports.unshift(record);
    }

    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(reports));
    } catch (e) {
      console.warn('Failed to save citizen report to localStorage', e);
    }
    return record;
  },

  updateReportStatus(id: string, fresh: Partial<Incident>): CitizenReportRecord | null {
    const reports = this.getReports();
    const index = reports.findIndex(r => r.id === id);
    if (index === -1) return null;

    reports[index] = {
      ...reports[index],
      status: fresh.status || reports[index].status,
      severity: fresh.severity || reports[index].severity,
      category: fresh.category || reports[index].category,
      assigned_unit_id: fresh.assigned_unit_id !== undefined ? fresh.assigned_unit_id : reports[index].assigned_unit_id,
      updated_at: new Date().toISOString(),
    };

    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(reports));
    } catch {}
    return reports[index];
  },

  deleteReport(id: string): void {
    const reports = this.getReports().filter(r => r.id !== id);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(reports));
    } catch {}
  },

  clearAll(): void {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {}
  }
};
