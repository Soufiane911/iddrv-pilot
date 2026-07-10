import { render, screen, waitFor } from '@testing-library/react';
import { App } from '../App';
import { mockApiClient } from '../lib/api';

test('affiche le shell multi-site et le catalogue atelier', async () => {
  window.history.pushState({}, '', '/sites');
  render(<App api={mockApiClient} />);
  expect(screen.getByText('IDDRV')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /Vos ateliers/i })).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText('Usine Principale')).toBeInTheDocument());
  expect(screen.getByRole('button', { name: /Ouvrir l’atelier/i })).toBeInTheDocument();
});

test('ouvre le plan 2D et expose les presses au clavier', async () => {
  window.history.pushState({}, '', '/sites/1/workshop');
  render(<App api={mockApiClient} />);
  await waitFor(() => expect(screen.getByRole('img', { name: /Plan 2D de l’atelier/i })).toBeInTheDocument());
  expect(screen.getByRole('button', { name: /Presse 152/i })).toBeInTheDocument();
  expect(screen.getByLabelText(/Position dans la période historique/i)).toBeInTheDocument();
});
