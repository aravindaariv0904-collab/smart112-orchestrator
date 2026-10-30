import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { IncidentDetail } from './IncidentDetail';
import { api } from '../services/api';
import type { Incident, RecommendationResponse } from '../types';

vi.mock('../services/api', () => ({
  api: {
    getRecommendations: vi.fn(),
    approveDispatch: vi.fn(),
    updateUnitStatus: vi.fn(),
  },
}));

const recommendation: RecommendationResponse = {
  incident_id: 'inc-a',
  candidate_units: [
    {
      unit_id: 'unit-a',
      callsign: 'AMB-VJW-01',
      type: 'AMBULANCE',
      distance_km: 2.01,
      eta_minutes: 3,
      status: 'AVAILABLE',
      station: 'Vijayawada Old City General Hospital',
      latitude: 16.5062,
      longitude: 80.648,
    },
  ],
  rationale: 'Unit AMB-VJW-01 prioritized by distance.',
};

const assessedIncident: Incident = {
  id: 'inc-a',
  incident_number: 'INC-2026-0100',
  description: 'Someone is hurt near the temple, exact address unknown.',
  category: 'GENERAL_EMERGENCY',
  status: 'ASSESSED',
  severity: 'LEVEL_2_HIGH',
  latitude: 16.52,
  longitude: 80.64,
  address: 'Coordinates only (no address supplied)',
  requires_human_review: true,
  assessment_data: JSON.stringify({
    incident_type: 'GENERAL_EMERGENCY',
    casualty_count: 0,
    hazards: [],
    missing_information: ['Exact landmark or cross-street details missing'],
    severity: 'LEVEL_2_HIGH',
    confidence_score: 0.88,
    uncertainty_flags: ['AMBIGUOUS_LOCATION'],
    requires_human_review: true,
    potential_duplicate_of: 'INC-2026-0099',
    potential_duplicate_distance_meters: 30,
  }),
};

beforeEach(() => {
  vi.mocked(api.getRecommendations).mockReset();
  vi.mocked(api.getRecommendations).mockResolvedValue(recommendation);
});

describe('IncidentDetail', () => {
  it('shows missing-information, uncertainty, duplicate, and AI provenance labels', async () => {
    render(<IncidentDetail incident={assessedIncident} />);

    expect(await screen.findByText(/Information Deficits/i)).toBeInTheDocument();
    expect(screen.getByText(/Exact landmark or cross-street details missing/)).toBeInTheDocument();
    expect(screen.getByText('AMBIGUOUS_LOCATION')).toBeInTheDocument();
    expect(screen.getByText('POTENTIAL DUPLICATE REPORT DETECTED')).toBeInTheDocument();
    expect(screen.getByText(/INC-2026-0099/)).toBeInTheDocument();
    expect(screen.getByText(/88% \(model-reported\)/)).toBeInTheDocument();
    expect(await screen.findByText('Confirm & Dispatch AMB-VJW-01')).toBeInTheDocument();
    expect(screen.queryByText('CRITICAL RESOURCE SHORTAGE')).not.toBeInTheDocument();
  });

  it('does not report a resource shortage for an already-dispatched incident', async () => {
    render(
      <IncidentDetail
        incident={{
          ...assessedIncident,
          status: 'DISPATCHED',
          assigned_unit_id: 'unit-a',
          assigned_unit_callsign: 'AMB-VJW-01',
          assigned_unit_type: 'AMBULANCE',
        }}
      />
    );

    expect(screen.getByText('Matching closed for this incident')).toBeInTheDocument();
    expect(screen.queryByText('CRITICAL RESOURCE SHORTAGE')).not.toBeInTheDocument();
    expect(api.getRecommendations).not.toHaveBeenCalled();
  });

  it('renders a matcher failure as an error, not as zero available units', async () => {
    vi.mocked(api.getRecommendations).mockRejectedValue(new Error('matcher timeout'));
    render(<IncidentDetail incident={assessedIncident} />);

    expect(await screen.findByText('UNIT MATCHING UNAVAILABLE')).toBeInTheDocument();
    expect(screen.queryByText('CRITICAL RESOURCE SHORTAGE')).not.toBeInTheDocument();
    expect(screen.getByText(/matcher timeout/)).toBeInTheDocument();
  });

  it('renders caller voice guidance and follow-up question widgets', async () => {
    render(<IncidentDetail incident={assessedIncident} />);
    expect(screen.getByText(/Caller Voice Guidance Advisory/i)).toBeInTheDocument();
    expect(screen.getByText('CPR Assist')).toBeInTheDocument();
    expect(screen.getByText('Fire Evac')).toBeInTheDocument();
    expect(screen.getByText('Bleed Stop')).toBeInTheDocument();
    expect(screen.getByText(/Targeted Triage Follow-up Questions/i)).toBeInTheDocument();
    expect(screen.getByText('Analyze Gaps')).toBeInTheDocument();
  });

  it('discards the previous unit selection when the selected incident changes', async () => {
    const { rerender } = render(<IncidentDetail incident={assessedIncident} />);
    expect(await screen.findByText('Confirm & Dispatch AMB-VJW-01')).toBeInTheDocument();

    vi.mocked(api.getRecommendations).mockResolvedValue({
      incident_id: 'inc-b',
      candidate_units: [
        {
          ...recommendation.candidate_units[0],
          unit_id: 'unit-b',
          callsign: 'AMB-GNT-03',
        },
      ],
      rationale: 'Second incident candidate.',
    });

    rerender(
      <IncidentDetail
        incident={{
          ...assessedIncident,
          id: 'inc-b',
          incident_number: 'INC-2026-0101',
        }}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Confirm & Dispatch AMB-GNT-03')).toBeInTheDocument();
    });
    expect(screen.queryByText('Confirm & Dispatch AMB-VJW-01')).not.toBeInTheDocument();
  });
});
