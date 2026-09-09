import { fireEvent, render, screen, within } from '@testing-library/react';
import { App } from '../App';
import { mockApiClient } from '../lib/api';

test('expose le planning comme parcours principal indépendant', async () => {
  window.history.pushState({}, '', '/overview');
  render(<App api={mockApiClient} />);
  const navigation = await screen.findByRole('navigation', { name: 'Navigation métier' });
  expect(within(navigation).getAllByRole('link').map((link) => link.getAttribute('href')))
    .toEqual(['/overview', '/sites', '/incidents', '/planning', '/imports']);
  expect(within(navigation).queryByRole('link', { name: /Nouvel import/i })).not.toBeInTheDocument();
});

test('relie les outils entre eux et conserve le titre de la page consultée', async () => {
  window.history.pushState({}, '', '/health');
  render(<App api={mockApiClient} />);
  const navigation = await screen.findByRole('navigation', { name: 'Outils techniques' });
  expect(within(navigation).getByRole('link', { name: 'Santé des services' })).toHaveAttribute('aria-current', 'page');
  fireEvent.click(within(navigation).getByRole('link', { name: 'Suivi HDT' }));
  expect(await screen.findByRole('heading', { level: 1, name: 'Suivi du modèle HDT' })).toBeInTheDocument();
  expect(within(screen.getByRole('navigation', { name: 'Outils techniques' })).getByRole('link', { name: 'Suivi HDT' })).toHaveAttribute('aria-current', 'page');
  fireEvent.click(screen.getByRole('link', { name: 'Profil et accès' }));
  expect(await screen.findByRole('heading', { level: 1, name: 'Profil et accès' })).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /Démonstration/i })).not.toBeInTheDocument();
});

test('redirige les anciennes opportunités fictives vers les incidents', async () => {
  window.history.pushState({}, '', '/sites/1/opportunities');
  render(<App api={mockApiClient} />);
  expect(await screen.findByRole('heading', { name: 'Incidents à examiner' })).toBeInTheDocument();
  expect(window.location.pathname).toBe('/incidents');
  expect(screen.queryByText('Opportunités de gain')).not.toBeInTheDocument();
});
