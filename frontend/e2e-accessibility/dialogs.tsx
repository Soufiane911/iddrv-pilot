// Browser fixture: real editors/providers/styles, only persistence is intercepted.
import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { AppTestShell } from '../src/App';
import { mockApiClient } from '../src/lib/api';
import { PressFormDrawer } from '../src/components/workshop/PressFormDrawer';
import { ProductionAssignmentEditor } from '../src/components/planning/ProductionAssignmentEditor';
import '../src/components/planning/planning.css';

const machines = [{ id: 606, siteId: 1, name: 'Presse audit', erpRef: '606' }];
async function save(): Promise<never> {
  await fetch('/a11y-save', { method: 'POST' });
  throw new Error('Refus simulé après attente');
}
const api = { ...mockApiClient, createMachine: save, createWorkOrder: save };
function Harness() {
  const [kind, setKind] = useState<string | null>(null);
  const close = () => setKind(null);
  return <><button onClick={() => setKind('press')}>Ouvrir presse</button><button onClick={() => setKind('planning')}>Ouvrir planning</button>
    <PressFormDrawer api={api} siteId={1} open={kind === 'press'} onClose={close} onSaved={close} />
    <ProductionAssignmentEditor siteId={1} timezone="Europe/Paris" machines={machines} open={kind === 'planning'} canPlan onClose={close} onSaved={close} />
  </>;
}
createRoot(document.getElementById('root')!).render(<AppTestShell api={api}><BrowserRouter><Harness /></BrowserRouter></AppTestShell>);
