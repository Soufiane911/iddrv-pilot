# Conservation, tri et exercice synthétique

## Politique proposée, inactive

Aucune durée juridique approuvée. Les champs `duree_active`, `duree_archive`, base et responsable du [registre](registre.json) restent null : **aucune purge réelle ne doit en découler**. Le seuil temporel de l'exercice est une donnée pédagogique fixe, pas une recommandation de durée. Les catégories non prises en charge sont exclues, jamais supprimées par défaut.

| Périmètre | Tri/minimisation à appliquer après décision | Fréquence proposée, à approuver |
|---|---|---|
| Comptes/rôles/sessions | Revue habilitations, départs, révocations ; isoler sessions globales et comptes multi-site ; conserver références auteur nécessaires | À chaque départ/changement, revue mensuelle |
| Imports/staging/rejets/raw/uploads | Qualifier colonnes inutiles, textes et copies ; échéance à partir d'un état terminal et besoin de reprise terminé ; blocage en cas de référence/audit/suspension | Inventaire mensuel, aperçu hebdomadaire des échéances approuvées |
| Cycles/ERP/contextes | Séparer mesure industrielle et identifiant opérateur ; agrégats non automatiquement anonymes ; respecter révisions et triggers | Revue mensuelle, à chaque changement de source |
| Feedback/incidents/planning/audit | Réduire commentaires, déterminer nécessité de l'auteur et des snapshots ; dissociation uniquement après arbitrage technique/juridique | À clôture/demande de droit ; revue trimestrielle proposée |
| Exports/ML | Inventorier destinataires/copies, limiter colonnes et petits groupes identifiants ; retirer jeux obsolètes selon décisions | À chaque export/version modèle et revue mensuelle |
| Logs/Redis/sauvegardes | Définir rotation, active/archive et protections ; traiter AOF, copies et restauration, pas seulement TTL | Contrôle hebdomadaire ; contrôle anti-réintroduction à chaque restauration |

Suspensions : litige, demande en cours, incident de sécurité ou obligation de preuve doivent être qualifiés et datés par une personne compétente ; pas de conservation perpétuelle par défaut. Dans le simulateur, **toutes les décisions mapping sont conservées** par prudence, sans leur attribuer une obligation légale. Les audits réels, comptes, sites, presses, incidents, cycles et fichiers disque sont hors périmètre du simulateur.

## Procédure réelle à concevoir, pas un mode caché du script

1. Responsable nommé approuve fiche/justification/durée/déclencheur et exceptions. Inventaire des copies et minimisation à la collecte ; ne jamais publier les valeurs.
2. Relever version schéma et GRANT sur environnement autorisé ; inventaire en lecture seule, transaction READ ONLY, contraintes site et contexte explicites, comptes/catégories/échéances sans contenu. Comparer dépendances SQL réelles (FK, triggers, vues, agrégats, index) et références JSON/fichiers hors FK.
3. Lot approuvé distinctement : borne UTC, état terminal, site, catégories, comptages attendus, suspensions et copies concernées. Une valeur inconnue bloque. Pas d'unique `DELETE WHERE date < ...` transversal.
4. Test sur PostgreSQL/Timescale **neuf et synthétique** : enfants avant parents ; références partagées restent protégées ; pas de suppression sites/presses (022), pas de désactivation des triggers historiques (016/019), pas d'utilisation de `iddrv.allow_tenant_delete` comme raccourci. La référence courante ERP crée un cycle de dépendance à résoudre avec le concepteur, pas par cascade aveugle. Un reçu push peut supprimer des cycles par CASCADE (021) ; recalcul/effacement agrégats à traiter explicitement.
5. Prévoir transaction, limites de lot/verrous/concurrence et rollback SQL ; pour fichiers, protocole séparé de reprise car suppression disque non transactionnelle avec SQL. Refuser chemins arbitraires et liens symboliques, exiger stockage dédié et manifeste autorisé ; **aucun mécanisme fichiers livré ici**.
6. Vérifier restauration synthétique et non-réintroduction avant adaptation réelle. Sauvegarde préalable réelle éventuelle doit elle-même avoir durée et accès approuvés : ne pas créer une copie éternelle des données à effacer.
7. Rapport minimal signé : règle/version, approbateur, date UTC, site, compteurs avant/après, suspensions, anomalies et reprise ; aucune donnée personnelle/secret dans la preuve. Les logs de purge ont leur propre politique.

## Exercice reproductible livré

[Script](../../../scripts/certification/rgpd/synthetic_purge.py), Python 3.10+ et bibliothèque standard SQLite uniquement ; aucun Docker, service, dépendance pip, variable d'environnement, DSN ou fichier d'entrée. Le processus construit **sa propre base SQLite `:memory:` neuve**, cinq relations réduites issues de SQL 005/004/init, puis la détruit à la fermeture. Il n'accepte pas de connexion externe ni de chemin d'upload et ne suit aucun symlink de données.

**Ce n'est ni un import métier, ni le MPD PostgreSQL, ni une purge du système existant.** Les relations réduites omettent colonnes métier/contraintes PostgreSQL et utilisent des FK restrictives au lieu de cascades pour montrer un ordre explicite. La fixture importe 2 sites, 1 utilisateur fictif, 6 dossiers, 6 métadonnées fichier, 1 décision. Aucun véritable fichier XLSX n'est créé.

Depuis la racine du dépôt :

```sh
POLICY='{"context":"synthetic-workspace-v1","site_id":1,"cutoff_utc":"2026-01-01T00:00:00Z","as_of_utc":"2026-02-01T00:00:00Z","decision_policy":"preserve_all","status":"failed"}'
python3 scripts/certification/rgpd/synthetic_purge.py --policy-json "$POLICY"
python3 scripts/certification/rgpd/synthetic_purge.py --policy-json "$POLICY" --execute-synthetic --confirm ERASE_SYNTHETIC_WORKSPACE_ONLY
python3 -m unittest discover -s tests -p 'test_certification_rgpd*.py' -v
python3 scripts/certification/rgpd/schema_inventory.py
```

Le dry-run ne fait que SELECT/BEGIN/ROLLBACK **après le seed en mémoire**, sans mutation de la fixture. L'exécution exige un drapeau et la confirmation exacte ; l'effet reste limité à la mémoire du processus. Le JSON de politique doit avoir exactement les six clés : contexte fixe, site entier 1 ou 2 (pas booléen/SQL), borne UTC stricte `Z` ou `+00:00`, date d'observation postérieure, décisions préservées, état `failed`. Les dates locales/décalées/invalides et politiques partielles sont refusées ; convertir explicitement une date locale en UTC avant de proposer une politique. Éligibilité : `updated_at < cutoff`, état failed, site choisi et aucune décision référençant le dossier **ou ses fichiers**. À égalité la donnée reste conservée.

## Compte rendu de l'exercice

Exécution locale sur base `59a4846b` + fichiers C4 : commandes ci-dessus, voir résultats dans [README](README.md). Attendus vérifiés : 1 dossier et 1 métadonnée fichier candidats ; 1 dossier ancien suspendu par décision ; frontière exacte, donnée récente, dossier actif et autre site conservés. Dry-run : 6/6 dossiers/fichiers avant et après. Exécution : 6/6 → 5/5 ; sites 2, utilisateurs 1, décisions 1 inchangés. Suppression enfants puis parent dans une transaction ; erreur injectée entre les deux restaure intégralement la fixture.

Sauvegardes : aucune sauvegarde utilisateur créée ou lue, aucune restauration réelle exécutée ; la fixture est régénérable, snapshots avant/après restent en mémoire. Aucune ressource Docker/réseau créée. Les captures temporaires éventuelles sont uniquement des compteurs synthétiques dans `/tmp/iddrv-c4-f7bb` ; pas de logs privés versionnés. Non testé : contraintes Timescale réelles, concurrence PostgreSQL, purge uploads, archivage physique Redis, export destinataire et restauration multi-supports.
