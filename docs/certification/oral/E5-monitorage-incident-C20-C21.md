# Épreuve E5 — Monitorage et résolution d’un incident

**Compétences :** C20 et C21 — **Durée :** 10 minutes  
**Message central :** IDDRV détecte les erreurs d’ingestion, conserve leur trace et permet une reprise sans corrompre les données métier.

## Incident conseillé

**Cas reconstitué :** dépôt d’un fichier industriel corrompu ou non reconnu. Le qualifier explicitement d’incident reconstitué en environnement de test.

## Déroulé conseillé

1. **Surveillance — 2 min**
   - Healthchecks Docker, endpoint `/health`, logs structurés et statuts d’import.
   - Cycle `inbox → processing → archive/quarantine`, retries et reprise après redémarrage.

2. **Déclenchement et impact — 1 min 30**
   - Le profiler ne reconnaît pas suffisamment le format.
   - L’import métier est bloqué ; les données existantes restent disponibles.

3. **Diagnostic — 2 min**
   - Consulter job et logs ; vérifier encodage, délimiteur, colonnes, structure et hash.
   - Vérifier qu’aucune transaction partielle n’a créé de données métier.

4. **Résolution — 2 min**
   - Quarantaine automatique, correction du fichier ou du mapping.
   - Relancer d’abord `probe` sans écriture, puis rejouer l’import validé.
   - Vérifier le statut final et l’absence de doublon.

5. **Tests et prévention — 1 min 30**
   - Tests de quarantaine, reprise et idempotence.
   - Mapping versionné et échantillon anonymisé de non-régression.

6. **Conclusion — 1 min**
   - Incident contenu, correction vérifiée et preuve conservée.

## Preuves à préparer

- Capture du fichier dans l’inbox et du statut de quarantaine.
- Extrait de log sans secret et résultat de `probe`.
- Test automatisé avant/après correction.
- Fiche d’incident datée avec impact, cause, correction et prévention.

## Fiche à compléter

| Champ | Valeur |
|---|---|
| Identifiant | À renseigner |
| Date et environnement | À renseigner |
| Déclenchement | Dépôt d’un fichier invalide |
| Impact | Import bloqué, données existantes intactes |
| Cause racine | À renseigner après reproduction |
| Correction | À renseigner |
| Vérification | Tests de quarantaine, reprise et idempotence |
| Prévention | `probe`, mapping versionné et test de non-régression |

## Questions probables

- Comment avez-vous détecté l’incident ?
- Comment prouvez-vous l’absence de données partielles ?
- Quelle différence entre retry et quarantaine ?
- Comment évitez-vous un double traitement ?
