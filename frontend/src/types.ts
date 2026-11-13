export type IncidentStatus = 
  | 'REPORTED'
  | 'ASSESSED'
  | 'RECOMMENDED'
  | 'DISPATCHED'
  | 'ON_SCENE'
  | 'RESOLVED'
  | 'CANCELLED';

export type SeverityLevel = 
  | 'LEVEL_1_CRITICAL'
  | 'LEVEL_2_HIGH'
  | 'LEVEL_3_MODERATE'
  | 'LEVEL_4_LOW';

export type UnitType = 
  | 'AMBULANCE'
  | 'FIRE_TRUCK'
  | 'POLICE_PATROL'
  | 'RESCUE_SQUAD';

export type UnitStatus = 
  | 'AVAILABLE'
  | 'DISPATCHED'
  | 'ON_SCENE';

export interface Incident {
  id: string;
  incident_number: string;
  description: string;
  category: string;
  status: IncidentStatus;
  severity: SeverityLevel;
  latitude: float;
  longitude: float;
  address?: string;
  requires_human_review?: boolean;
  assessment_data?: string;
  created_at?: string;
  updated_at?: string;
  assigned_unit_id?: string;
  assigned_unit_callsign?: string;
  assigned_unit_type?: string;
}

export type float = number;

export interface ExtractedFacts {
  incident_type?: string;
  casualty_count?: number;
  hazards?: string[];
  location_markers?: string[];
  missing_information?: string[];
  uncertainty_detected?: boolean;
  uncertainty_flags?: string[];
  potential_duplicate_of?: string;
  potential_duplicate_id?: string;
  potential_duplicate_distance_meters?: number;
  severity?: string;
  confidence_score?: number;
  requires_human_review?: boolean;
  structured_facts?: Record<string, any>;
  status?: string;
}

export interface CandidateUnit {
  unit_id: string;
  callsign: string;
  type: UnitType;
  distance_km: number;
  road_distance_km?: number;
  eta_minutes: number;
  eta_basis?: string;
  eta_confidence?: string;
  status: UnitStatus;
  station?: string;
  latitude: number;
  longitude: number;
}

export interface RecommendationResponse {
  incident_id: string;
  candidate_units: CandidateUnit[];
  rationale: string;
  location_status?: string;
  resource_deficit?: boolean;
}

export interface EmergencyUnit {
  id: string;
  callsign: string;
  unit_type: UnitType;
  latitude: number;
  longitude: number;
  status: UnitStatus;
  station?: string;
  updated_at?: string;
}

export interface AuditRecord {
  id: string;
  incident_id: string;
  actor: string;
  action: string;
  details: string;
  timestamp?: string;
}

export interface AudioTranscribeResult {
  filename: string;
  size_bytes: number;
  transcription_status?: string;
  transcript: string;
  language: string;
  stt_confidence: number;
  extracted_facts: ExtractedFacts;
  requires_human_review?: boolean;
}

export interface Facility {
  id: string;
  facility_id?: string;
  name: string;
  facility_type: string;
  subtype?: string;
  address: string;
  latitude: number;
  longitude: number;
  phone?: string;
  email?: string;
  timezone?: string;
  has_emergency: boolean;
  has_icu: boolean;
  has_operating_theatre?: boolean;
  bed_count?: number;
  available_beds?: number;
  icu_beds_available?: number;
  general_beds_available?: number;
  blood_types_available?: string[];
  description?: string;
  operating_hours?: string;
  is_active: boolean;
  distance_km?: number;
}
