import { 
  Incident, 
  EmergencyUnit, 
  RecommendationResponse, 
  AuditRecord, 
  AudioTranscribeResult 
} from '../types';

const API_BASE = '/api/v1';

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };

  const response = await fetch(url, { ...options, headers });
  
  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorJson = await response.json();
      if (errorJson.detail) {
        errorDetail = errorJson.detail;
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export const api = {
  async getHealth(): Promise<{ status: string; ssot_enforced: boolean; zero_cost_stack: boolean }> {
    return request('/health');
  },

  async getIncidents(statusFilter?: string): Promise<Incident[]> {
    const query = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : '';
    return request<Incident[]>(`/incidents${query}`);
  },

  async getIncident(id: string): Promise<Incident> {
    return request<Incident>(`/incidents/${id}`);
  },

  async createIncident(payload: {
    description: string;
    latitude: number;
    longitude: number;
    address?: string;
  }): Promise<Incident> {
    return request<Incident>('/incidents', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  async purgeAllIncidents(): Promise<{ status: string; message: string; incident_count: number }> {
    return request<{ status: string; message: string; incident_count: number }>('/incidents/purge-all', {
      method: 'DELETE'
    });
  },

  async getRecommendations(incidentId: string): Promise<RecommendationResponse> {
    return request<RecommendationResponse>(`/incidents/${incidentId}/recommend`, {
      method: 'POST'
    });
  },

  async approveDispatch(
    incidentId: string, 
    unitId: string, 
    dispatcherId: string = 'DISPATCHER_SARAH',
    notes?: string
  ): Promise<any> {
    return request(`/incidents/${incidentId}/approve-dispatch`, {
      method: 'POST',
      body: JSON.stringify({
        unit_id: unitId,
        dispatcher_id: dispatcherId,
        notes: notes || 'Authorized deployment via Dispatcher Console'
      })
    });
  },

  async getUnits(typeFilter?: string, statusFilter?: string): Promise<EmergencyUnit[]> {
    const params = new URLSearchParams();
    if (typeFilter) params.append('unit_type', typeFilter);
    if (statusFilter) params.append('unit_status', statusFilter);
    const query = params.toString() ? `?${params.toString()}` : '';
    return request<EmergencyUnit[]>(`/units${query}`);
  },

  async updateUnitStatus(
    unitId: string, 
    status: string, 
    dispatcherId: string = 'DISPATCHER_SARAH', 
    notes?: string
  ): Promise<any> {
    return request(`/units/${unitId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({
        status,
        dispatcher_id: dispatcherId,
        notes
      })
    });
  },

  async getAuditTrail(incidentId: string): Promise<AuditRecord[]> {
    return request<AuditRecord[]>(`/audit/${incidentId}`);
  },

  async transcribeAudio(file: File): Promise<AudioTranscribeResult> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/audio/transcribe`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      let msg = `Upload failed with status ${response.status}`;
      try {
        const err = await response.json();
        if (err.detail) msg = err.detail;
      } catch {}
      throw new Error(msg);
    }

    return response.json();
  }
};

