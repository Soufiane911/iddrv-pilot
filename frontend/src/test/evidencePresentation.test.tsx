import { render, screen, within } from '@testing-library/react';
import { App } from '../App';
import { mockApiClient, type Evidence } from '../lib/api';

const evidence: Evidence = {
  id: 'proof-rate', source_kind: 'cycle_aggregate', source_ref: '152:OF-12', metric: 'scrap_rate',
  window: { start: '2025-02-12T00:21:43Z', end: '2025-02-12T01:52:40Z' },
  observation: { stat: 'rate', value: 0.4, unit: 'fraction', n: 30 },
  baseline: { value: 0.024, unit: 'fraction' }, delta: 0.376, supports: true,
};

function renderEvidence(items: Evidence[]) {
  window.history.pushState({}, '', '/incidents/s001-demo');
  return render(<App api={{ ...mockApiClient, getEvidence: async () => items }} />);
}

test('rend les fractions en pourcentages et les effectifs sans unité physique', async () => {
  renderEvidence([evidence]);
  const label = await screen.findByText('Taux de rebut');
  const row = label.closest('details')!;
  expect(row).not.toHaveAttribute('open');
  expect(within(row).getByText('Taux : 40,0 %')).toBeInTheDocument();
  expect(within(row).getByText('Référence : 2,4 %')).toBeInTheDocument();
  expect(within(row).getByText('Écart : 37,6 points de pourcentage')).toBeInTheDocument();
  expect(within(row).getByText(/Observations : 30$/)).toBeInTheDocument();
  expect(within(row).queryByText(/30,00 fraction/)).not.toBeInTheDocument();
  expect(row.querySelector('time')).toHaveAttribute('datetime', evidence.window.start);
  expect(within(row).getByText('proof-rate')).toBeInTheDocument();
});

test('distingue une variabilité de température d’une température mesurée', async () => {
  renderEvidence([{ ...evidence, metric: 'mold_temperature_c', observation: { stat: 'stdev', value: 7.01, unit: 'C', n: 30 }, baseline: { value: 5.98, unit: 'C' }, delta: 1.03 }]);
  const row = (await screen.findByText('Température du moule')).closest('details')!;
  expect(within(row).getByText('Écart-type : 7,01 °C')).toBeInTheDocument();
  expect(within(row).getByText('Référence : 5,98 °C')).toBeInTheDocument();
  expect(within(row).getByText(/Observations : 30$/)).toBeInTheDocument();
});
