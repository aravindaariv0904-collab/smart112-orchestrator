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
    'X-Dispatcher-Token': 'smart112-dispatch-key-2026',
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
    dispatcherId: string = 'DISPATCHER_GNT_01',
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
    dispatcherId: string = 'DISPATCHER_GNT_01',
    notes?: string
  ): Promise<any> {
    return request(`/units/${unitId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({
        status,
        dispatcher_id: dispatcherId,
        notes: notes || `Unit status updated to ${status}`
      })
    });
  },

  async getAuditLog(incidentId: string): Promise<AuditRecord[]> {
    return request<AuditRecord[]>(`/audit/${incidentId}`);
  },

  async getAuditTrail(incidentId: string): Promise<AuditRecord[]> {
    return this.getAuditLog(incidentId);
  },

  async uploadAudio(file: File): Promise<AudioTranscribeResult> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/audio/transcribe`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      let errorDetail = `Audio upload failed (${response.status})`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) errorDetail = errorJson.detail;
      } catch {
        // ignore
      }
      throw new Error(errorDetail);
    }

    return response.json();
  },

  async transcribeAudio(file: File): Promise<AudioTranscribeResult> {
    return this.uploadAudio(file);
  },

  // BUG-08: Text-to-Speech Guidance
  async synthesizeGuidance(guidanceType: string = 'CPR_ASSIST', customText?: string, language: string = 'en'): Promise<any> {
    return request('/audio/synthesize-guidance', {
      method: 'POST',
      body: JSON.stringify({
        guidance_type: guidanceType,
        custom_text: customText,
        language
      })
    });
  },

  async getGuidanceTemplates(): Promise<{ templates: Array<{ type: string; advisory: string }> }> {
    return request('/audio/guidance-templates');
  },

  // BUG-09: VLM Scene Image Analysis
  async analyzeSceneImage(file: File): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/vision/analyze`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      let errorDetail = `Image analysis failed (${response.status})`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) errorDetail = errorJson.detail;
      } catch {
        // ignore
      }
      throw new Error(errorDetail);
    }

    return response.json();
  },

  // BUG-10: Spatio-temporal Incident Duplicates
  async getIncidentDuplicates(incidentId: string): Promise<any> {
    return request(`/incidents/${incidentId}/duplicates`);
  },

  // BUG-11: Targeted Follow-up Questions
  async getFollowUpQuestions(incidentId: string): Promise<any> {
    return request(`/incidents/${incidentId}/follow-up-questions`, {
      method: 'POST'
    });
  },

  // BUG-12: Unit Telemetry
  async getUnitTelemetry(unitId: string): Promise<any> {
    return request(`/units/${unitId}/telemetry`);
  },

  // BUG-13: Multi-agent Workflow
  async runMultiAgentWorkflow(transcript: string, latitude: number, longitude: number): Promise<any> {
    return request('/orchestrator/triage-workflow', {
      method: 'POST',
      body: JSON.stringify({
        transcript,
        latitude,
        longitude
      })
    });
  },

  // BUG-14: Real Database Analytics Dashboard
  async getDashboardAnalytics(): Promise<any> {
    return request('/analytics/dashboard');
  }
};
