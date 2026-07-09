import { render, screen } from '@testing-library/react';
import { App } from '../App';
test('affiche le shell et la vue atelier', () => { window.history.pushState({}, '', '/'); render(<App />); expect(screen.getAllByText('Vue atelier')).toHaveLength(2); expect(screen.getByText('IDDRV')).toBeInTheDocument(); });
