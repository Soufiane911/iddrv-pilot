import './workshopSetup.css';

interface SiteSetupChecklistProps {
  hasPresses: boolean;
  canConfigure: boolean;
  canImport: boolean;
  onAddPress: () => void;
  onConfigureGateway: () => void;
  onImportErp: () => void;
}

export function SiteSetupChecklist({ hasPresses, canConfigure, canImport, onAddPress, onConfigureGateway, onImportErp }: SiteSetupChecklistProps) {
  return <section className="workshop-setup-card" aria-labelledby="workshop-setup-title">
    <header>
      <p className="eyebrow">MISE EN SERVICE</p>
      <h2 id="workshop-setup-title">Préparer cet atelier</h2>
      <p>Commencez par déclarer le parc. L’ERP et la collecte peuvent être configurés plus tard.</p>
    </header>
    <ol className="workshop-checklist">
      <li className="complete"><span className="workshop-checklist-marker" aria-hidden="true">✓</span><span><strong>Site créé</strong><small>Le site et son fuseau sont disponibles.</small></span></li>
      <li className={hasPresses ? 'complete' : undefined}><span className="workshop-checklist-marker" aria-hidden="true">2</span><span><strong>Ajouter les presses</strong><small>Créez une presse avec son nom et son code atelier.</small></span><button className="button-secondary" type="button" onClick={onAddPress} disabled={!canConfigure}>Ajouter une presse</button></li>
      <li><span className="workshop-checklist-marker" aria-hidden="true">3</span><span><strong>Créer la passerelle</strong><small>La passerelle locale regroupera les boîtiers de presses.</small></span><button className="button-secondary" type="button" onClick={onConfigureGateway}>Configurer la passerelle</button></li>
      <li><span className="workshop-checklist-marker" aria-hidden="true">4</span><span><strong>Mapper les identifiants détectés</strong><small>Cette étape sera disponible après la première détection source.</small></span></li>
      <li><span className="workshop-checklist-marker" aria-hidden="true">5</span><span><strong>Vérifier le premier cycle</strong><small>Les cycles reçus resteront consultables dans l’atelier.</small></span></li>
    </ol>
    <div className="workshop-setup-actions">
      <button className="button-primary" type="button" onClick={onAddPress} disabled={!canConfigure}>Ajouter une presse</button>
      <button className="button-secondary" type="button" onClick={onConfigureGateway}>Configurer la passerelle</button>
      <button className="button-secondary" type="button" onClick={onImportErp} disabled={!canImport}>Importer l’ERP</button>
    </div>
    {!canConfigure && <p className="helper-text" role="note">Votre rôle permet la lecture de l’atelier, mais pas sa configuration.</p>}
    {!canImport && canConfigure && <p className="helper-text" role="note">Votre rôle ne permet pas de lancer un import ERP.</p>}
  </section>;
}
