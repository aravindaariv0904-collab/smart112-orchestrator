import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { IncidentList } from './IncidentList';
import type { Incident } from '../types';

const incidents: Incident[] = [
  {
    id: '1',
    incident_number: 'INC-2026-0001',
    description: 'Multi-vehicle collision near the bus station.',
    category: 'TRAFFIC_ACCIDENT',
    status: 'DISPATCHED',
    severity: 'LEVEL_1_CRITICAL',
    latitude: 16.3,
    longitude: 80.4,
    address: 'Guntur RTC Bus Station',
    requires_human_review: true,
  },
  {
    id: '2',
    incident_number: 'INC-2026-0002',
    description: 'Someone is hurt near the big temple.',
    category: 'GENERAL_EMERGENCY',
    status: 'ASSESSED',
    severity: 'LEVEL_2_HIGH',
    latitude: 16.5,
    longitude: 80.6,
    address: 'Coordinates only (no address supplied)',
    requires_human_review: true,
  },
  {
    id: '3',
    incident_number: 'INC-2026-0003',
    description: 'Minor fender bender, no injuries reported.',
    category: 'TRAFFIC_ACCIDENT',
    status: 'RESOLVED',
    severity: 'LEVEL_4_LOW',
    latitude: 16.4,
    longitude: 80.5,
    address: 'Benz Circle',
    requires_human_review: false,
  },
];

describe('IncidentList', () => {
  it('filters to critical incidents only', () => {
    render(
      <IncidentList
        incidents={incidents}
        selectedIncident={null}
        onSelectIncident={vi.fn()}
        isLoading={false}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Critical (1)' }));

    expect(screen.getByText('INC-2026-0001')).toBeInTheDocument();
    expect(screen.queryByText('INC-2026-0002')).not.toBeInTheDocument();
    expect(screen.queryByText('INC-2026-0003')).not.toBeInTheDocument();
  });

  it('searches narrative and address text', () => {
    render(
      <IncidentList
        incidents={incidents}
        selectedIncident={null}
        onSelectIncident={vi.fn()}
        isLoading={false}
      />
    );

    fireEvent.change(screen.getByPlaceholderText(/Search emergency logs/), {
      target: { value: 'temple' },
    });

    expect(screen.getByText('INC-2026-0002')).toBeInTheDocument();
    expect(screen.queryByText('INC-2026-0001')).not.toBeInTheDocument();
  });

  it('selects an incident with the keyboard', () => {
    const onSelectIncident = vi.fn();
    render(
      <IncidentList
        incidents={incidents}
        selectedIncident={null}
        onSelectIncident={onSelectIncident}
        isLoading={false}
      />
    );

    const card = screen.getByText('INC-2026-0001').closest('[role="button"]');
    expect(card).not.toBeNull();
    fireEvent.keyDown(card!, { key: 'Enter' });

    expect(onSelectIncident).toHaveBeenCalledWith(incidents[0]);
  });

  it('shows an explicit empty state when no incident matches', () => {
    render(
      <IncidentList
        incidents={incidents}
        selectedIncident={null}
        onSelectIncident={vi.fn()}
        isLoading={false}
      />
    );

    fireEvent.change(screen.getByPlaceholderText(/Search emergency logs/), {
      target: { value: 'no-such-incident' },
    });

    expect(screen.getByText('No Incidents Found')).toBeInTheDocument();
  });
});
