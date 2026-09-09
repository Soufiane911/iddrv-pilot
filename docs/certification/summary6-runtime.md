# Summary6 — moteur expérimental autonome, phase 1

## Périmètre et statut scientifique

Aucun changement API, frontend, DB, déploiement, catalogue ou modèle historique.
Seul summary6 est implémenté; aucun autre candidat n'est activé. Le modèle
historique reste intact pour rollback. Ce moteur ne sélectionne pas le défaut
applicatif : le raccordement exclusif summary6 appartient à la phase 2.

Export choisi déterministement : `candidate_61007.joblib`, graine 42, premier
export, **pas meilleure graine**, pas données industrielles. Six contextes
synthétiques `M1/M2/M3 × R1/R2`. Aucun mapping vers des machines réelles.
Confirmation scientifique refusée : notamment FP/1000 = 14,18 sur 61008, plafond
10 dépassé. Ni certification usine, ni garantie de qualité prédictive, ni
prédiction de NOK futurs. Budget de calibration 0,0025 après persistance, pas
contamination IF ni garantie terrain. Références/seuils ne sont jamais réappris.

## Contrat public pour l'agent API suivant

Imports : `from ml.summary6 import load_package, score_cycles, UNITS`.

1. `load_package(directory, expected_manifest_sha256=TRUSTED_PIN)` vérifie
   manifeste, identité, code, environnement exact, contrat, références et SHA du
   payload **avant** désérialisation. Retourne `Package` avec `runtime_id`,
   `contexts`, `models`, `manifest`. Ne pas modifier ces objets après chargement.
   Le pin doit provenir de configuration approuvée, JAMAIS de la requête ou d'un
   upload. Joblib n'est pas un format sûr pour données non fiables. Le chargeur
   n'est pas un sandbox. Un paquet tiny est refusé sauf option explicite de test
   `allow_test_package=True` (interdite dans l'intégration applicative).
2. `score_cycles(cycles: list[dict], *, package) -> list[dict]`, un résultat par
   cycle en ordre d'entrée, appel stateless portant sur **un seul lot** :
   - Champs EXACTS : `source_id`, `machine_erp_ref`, `recipe_id`, `lot_id`
     (chaînes non vides constantes), `cycle_counter` (entier >=0, pas booléen),
     `units` (dictionnaire EXACT `UNITS`), `sensors` (dictionnaire des huit mesures).
   - Ordre capteurs : `cycle_time_s`, `injection_time_s`, `cooling_time_s`,
     `peak_pressure_bar`, `clamp_force_kn`, `mold_temperature_c`,
     `barrel_temp_zone2_c`, `energy_kwh`.
   - Unités : respectivement `s,s,s,bar,kN,degC,degC,kWh`. Pas de conversion ou
     d'imputation implicite. Mesures numériques seulement, booléens refusés;
     valeurs absentes/null/non finies donnent abstention causale dès leur cycle.
   - Préfixe contigu commençant à 20 ou avant. Pas besoin des cycles 0..19 si
     le préfixe commence exactement à 20. **20 derniers cycles seuls insuffisants**.
     Ne jamais renuméroter une fenêtre arbitraire pour fabriquer un lot.
   - Doublons, trous, ordre inversé, changement de lot/source/recette/machine,
     unités incorrectes, champs supplémentaires (dont labels/futur) :
     `ContractError(ValueError)`. Ne pas trier, segmenter ou réparer implicitement.
   - Nouveau lot = nouvel appel/préfixe, aucun état réutilisé. Pas de fallback.
     Recette/source doivent être celles connues au moment du cycle, non un ERP
     réconcilié ultérieurement. La phase 1 ne vérifie pas la vérité de ces IDs.
3. Chaque résultat contient : `runtime_id`, `cycle_counter`,
   `status=available|abstained`, `reason`, `model_scope=machine_recipe`,
   `features` (six nombres ou null), `instant_score`, `decision_score`,
   `threshold`, `alert` (booléen ou null), `signals=[]`.
   Aucune probabilité de défaut, horizon de qualité ou explication inventée.
   L'API devra ajouter ses IDs de requête/contexte sans changer cette sémantique.
   `reason` : `warmup`, `publication_warmup`, `incomplete_prefix`,
   `incomplete_sensors`, `unknown_context`, `anchor_out_of_guard`,
   `numerical_failure`, ou null.
   Conversion numérique contrôlée avant finitude : entiers JSON représentables
   acceptés, dépassement de float (ex. `10**400`) traité comme mesure non finie,
   donc `incomplete_sensors`, jamais TypeError/500. Booléens toujours refusés.
   `numerical_failure` : débordement/non-finitude de l'ancre/garde, résidus,
   huit moyennes ou huit écarts-types, six agrégats (dont RMS) ou scoring.
   Abstention persistante dès le cycle causal, scores/features/alerte nulls,
   sans effacer le passé. Aucun agrégat partiel à sept capteurs n'est autorisé.
   Les avertissements arithmétiques sont convertis en erreurs contrôlées,
   jamais ignorés; aucune limite métier arbitraire n'est ajoutée.
   Contexte inconnu : seuil et scores null. Une mesure manquante invalide le
   reste du préfixe de ce lot, pas les résultats antérieurs. Restaurer un préfixe
   corrigé exige un replay explicitement révisé, pas une correction silencieuse.

## Algorithme figé

Centre historique médian et échelle `1.4826*MAD` persistés par contexte.
Ancre locale médiane cycles 20..59, figée au cycle 59; garde strictement `>3`
écarts historiques maximaux (égalité 3 acceptée). Résidus `(mesure-ancre)/scale`
à partir de 60. Moyenne et std population `ddof=0` trailing20 via pandas rolling,
comme les sources (ne pas remplacer par un calcul approximativement équivalent).
Six agrégats ordonnés : maximum, RMS, quantile linéaire q75 des huit moyennes
absolues, puis maximum, RMS, q75 des huit std. Features dès 79.
`instant_score=-IF.score_samples`; `decision_score=min(3 scores successifs)` dès
81; publication/alerte uniquement >=84, comparaison `>=threshold`. Score brut
ne signifie pas décision publiable. Pas de recalibration ni d'entraînement.

## Sources / provenance

Sources locales lues uniquement, sous
`/Users/soufianehamzaoui/Desktop/EPSI/ProjetSeptembre/output/hdt-feature-hypotheses-2026-09-07/run01`.
Export SHA256 : `f70c137b944a04da6c8f1c405c4b217322019e60d3bb1e5d63066947d9a888ad`.
Gel sélection : `3e3112fff04a21272e8bb53ab5fcd0954bfd43279b5f10f5bb42a4ce628427c8`.
Port minimal (pas d'import output au runtime) :
- `source_snapshot/evaluate.py::make_features` :
  `4240750fa371ac95c54e889580a4b15dc5ced67d46c76892a32ba977e99cdace`.
- `hdt_methods.py::features,policy_scores` :
  `5054033b75b3332db199c82b1fd2bcfab6d9efb3ae297364a746dd49d9857f4f`.
- `feature_study.py::representations,decisions` :
  `c7b7742b0ca0c19fe28de008c310e8e7be49cd96bc7702617643441c3404be7c`.

L'exporteur vérifie les six snapshots contre `provenance.json`, vérifie le SHA
approuvé avant tout joblib.load, puis conserve seulement les modèles sklearn
standards dans le binaire. Références et seuils deviennent JSON. Aucun import ou
classe `output` nécessaire. Warnings de désérialisation/scoring fatals, notamment
incompatibilités sklearn. Aucun entraînement lourd ou campagne exécuté.

## Livraison privée et reproduction

Paquet durci hors Git : `/tmp/iddrv-summary6-package-hardened-0925d84d5446`.
- `manifest.json` : 5 431 octets, SHA256
  `919fc41c58d1e821f9dcf7e16ee6c317e5966d4ec1c2444ad96045289543f4ff`.
- `models.joblib` : 12 067 926 octets, SHA256
  `3de68e2dba256aab7e6d79d2acd6e0e74b915a20efe3046e5cbfeb22a696f915`.
- Runtime : `summary6-0c8b4c15cd4df33784468dfcd2057b52261122a8c90dbb0b1ba4a117b2870702`.

Copie durable privée effectuée dans un nouveau dossier nommé par l'identité
sans préfixe; permissions dossier0700/fichiers0600 et SHA des deux copies
vérifiés. Anciens paquets conservés sans modification.

« Compact » = modèles seuls + JSON; forêt non élaguée, toujours ~12 MB, aucun
binaire dans le patch. Parent : copier les DEUX fichiers vers un répertoire
privé neuf, vérifier les deux SHA, configurer le pin manifeste ci-dessus puis
charger avec EXACTEMENT le code livré. Ne pas copier le premier paquet de
travail sans suffixe `-final` : lié à une révision antérieure du code.
Tout changement des modules runtime invalide le paquet; repackager alors et
approuver une nouvelle identité. Une resérialisation peut changer les octets et
l'identité, même si les scores restent identiques; copier le paquet final pour
conserver cette identité, ne pas annoncer une reproductibilité binaire.

Commande exécutée :

    python3 scripts/package_summary6.py --destination /tmp/iddrv-summary6-package-hardened-0925d84d5446

Environnement effectivement testé/pinné : Python 3.13.9, sklearn 1.7.2,
numpy 2.2.6, pandas 2.3.3, scipy 1.16.3, joblib 1.5.2. Les métadonnées recherche
déclarent numpy 2.5.2/pandas 3.0.5 : ce n'est PAS le même environnement. Le
manifeste conserve les deux informations. L'équivalence numérique testée ici
ne prouve pas toutes plateformes/versions; loader strict, pas warning ignoré.

## Tests et limites explicites

Commande réelle, paquet approuvé :

    SUMMARY6_TEST_PACKAGE=/tmp/iddrv-summary6-package-hardened-0925d84d5446 SUMMARY6_TEST_MANIFEST_SHA256=919fc41c58d1e821f9dcf7e16ee6c317e5966d4ec1c2444ad96045289543f4ff python3 -m pytest -q tests/test_summary6_runtime.py tests/test_summary6_package.py

Résultat durci : **53 passed**. Sans variables : **51 passed, 2 skipped**.
33 nouveaux cas : `1e308`, `10**30`, `10**400` et booléens pour chacun des
huit capteurs, passé invariant, RMS débordant malgré moments finis.
CI : forêt tiny explicitement synthétique 3 arbres/16 observations par arbre,
fixture JSON limitée issue du lot synthétique M1-R1-L15, cycles20..90. Les six
features golden ont été générées par extraction AST des fonctions gelées,
indépendamment du port runtime. Scores golden calculés avec export approuvé;
CSV `predictions_61007_42_selected.csv.gz` vérifié à 1e-16 (limite décimale CSV).
Comparaisons runtime/fixture features, scores bruts, min3 : **array_equal**.

Les tests optionnels vérifient les scores réels sur cette trajectoire et
l'équivalence de resérialisation des six forêts/références/seuils sur features
golden + 128 sondes synthétiques. Ce n'est pas un replay exhaustif de tous les
lots/six contextes, ni une nouvelle confirmation scientifique. Les tests tiny
seuls ne certifient PAS les scores des forêts livrées. Autres tests : frontières,
prefixes causaux, futur manquant sans effet passé, resets, trous/doublons,
incohérence contexte/source, inconnus, unités, garde et seuil aux égalités,
tampering avant désérialisation, environnement/code/politique et reload.

Blocages phase 2 : fournir réellement historique contextualisé et causal,
identités lot/compteur/recette/unités, environnement compatible et stockage
privé durable. L'API/worker actuels à 20 cycles ne conviennent pas. Aucun changement
principal/push/merge ni activation d'autres candidats effectué.
