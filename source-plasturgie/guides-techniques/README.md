# Guides techniques — moulage par injection

Deux documents PDF sont présents dans ce répertoire. Cette fiche décrit ce qui a été vérifié localement et ne constitue pas une autorisation de republication.

## Vérifications communes

Le 2026-08-03, les deux fichiers ont été inspectés avec `file`, `pdfinfo` et `pdftotext -layout`. Ils sont lisibles, non chiffrés et le texte est extractible. `pdfinfo` signale toutefois des anomalies de structure (« Expected ... ») sur les deux fichiers ; elles n'empêchent pas l'extraction. Aucun document n'a été téléchargé pendant cette vérification et `data/scenarios/industrial_demo/ground_truth.json` n'a pas été consulté.

## 1. Characterizing Energy Consumption of the Injection Molding Process

**Fichier :** `nist_characterizing_energy_consumption_injection_molding_2013.pdf`

- **Titre :** *Characterizing Energy Consumption of the Injection Molding Process*.
- **Auteurs :** Jatinder Madan, Mahesh Mani et Kevin W. Lyons.
- **Organisme :** National Institute of Standards and Technology (NIST), Systems Integration Division (les deux premiers auteurs indiquent aussi leurs établissements universitaires).
- **Année :** 2013. Actes de l'ASME 2013 International Manufacturing Science and Engineering Conference (MSEC2013-1222), Madison, 10–14 juin 2013.
- **Source publique officielle :** [notice ASME via DOI](https://doi.org/10.1115/MSEC2013-1222). La page est une page éditeur ; elle ne signifie pas que le PDF intégral est librement redistribuable. Le catalogue [NIST Publications](https://www.nist.gov/publications) est également le point d'entrée institutionnel vérifié.
- **Droits/licence :** chaque page du PDF porte la mention : « This material is not subject to copyright protection. Approved for public release; distribution is unlimited ». C'est le seul statut retenu ici ; aucune licence SPDX ou licence de modification n'a été déduite. Le PDF contient aussi un disclaimer NIST sur les produits commerciaux.

### Utilité pour IDDRV

Le papier propose une méthode de caractérisation et non un jeu de mesures universel. Les variables exploitables sont notamment la géométrie (volume de la pièce, épaisseur maximale, nombre de cavités, runner/gate et matière), les propriétés matière (masse volumique, capacité calorifique, températures de fusion/injection/éjection, diffusivité thermique, chaleur latente, humidité et résistance au cisaillement), les consignes et capacités machine (pression, débit, force/course de fermeture, capacité d'injection et de plastification, type d'entraînement), ainsi que les temps d'injection, de refroidissement et de réarmement.

Les écarts/indicateurs process utiles sont le temps de cycle, l'énergie par cycle/shot et par pièce, l'énergie spécifique (kJ/kg), les pertes de transmission et de rendement des entraînements, la puissance de veille et les énergies auxiliaires (séchage, chargement, dosage/mélange, détourage). Le document sépare énergie minimale théorique et estimation plus réaliste, ce qui permet à IDDRV de conserver une valeur, une unité, un périmètre et une incertitude plutôt que de traiter une estimation comme une mesure.

### Limites

Les équations et facteurs sont une guideline analytique : plusieurs hypothèses sont idéalisées (par exemple COP de Carnot pour le minimum, facteur de 25 % pour certaines opérations, rendements représentatifs). L'article appelle lui-même à des études de cas réelles, à des frontières système explicites, à des modèles d'incertitude et à une méthodologie de référence. Il ne fournit donc pas de labels IDDRV ni de vérité terrain ; les valeurs doivent être recalées sur la machine, la matière, le moule et les mesures d'énergie disponibles.

## 2. Evaluation of an Injection Molding Process Model Using the Calculus of Imprecision to Simultaneously Specify Tolerances and Process Parameters

**Fichier :** `nist_injection_molding_process_model_tolerances_1997.pdf`

- **Titre :** *Evaluation of an Injection Molding Process Model Using the Calculus of Imprecision to Simultaneously Specify Tolerances and Process Parameters*.
- **Auteur :** Ronald E. Giachetti.
- **Organisme :** NIST, Manufacturing Systems Integration Division, Gaithersburg, Maryland (biographie incluse dans le document).
- **Année :** 1997 est l'année retenue par le nom du fichier fourni et les références/contexte du document ; aucune date de publication n'est imprimée sur la page de titre. Cette attribution doit être confirmée par une notice bibliographique externe avant citation formelle. `pdfinfo` indique seulement une création en 2005, qui est une date de production du PDF, pas une date de publication.
- **Source publique officielle retrouvée :** [catalogue NIST Publications](https://www.nist.gov/publications) (recherche à effectuer avec le titre exact). Aucun permalien NIST ou DOI correspondant au titre exact n'a été confirmé lors de cette vérification.
- **Droits/licence :** non déterminés. La présence d'un auteur NIST et la disponibilité d'une copie publique ne suffisent pas à établir le domaine public, une licence ouverte ou un droit de redistribution. Ne pas publier, transformer ou télécharger une nouvelle copie sans confirmation du détenteur des droits.

### Utilité pour IDDRV

Le modèle relie géométrie, matière et paramètres de procédé aux écarts dimensionnels : pression de compactage, température de moulage/fusion, volumes spécifiques au gel de seuil et au refroidissement, données PVT du polypropylène, retrait volumique et retrait linéaire (approximativement le tiers). Il distingue paramètres dépendants/indépendants et contrôlables/non contrôlables. Le *Calculus of Imprecision* utilise les opérateurs **image**, **domain** et **sufficient elements** pour propager des intervalles ou distributions de possibilité sans confondre plusieurs occurrences d'un même paramètre.

Pour un modèle IDDRV, cela suggère de stocker consignes et plages (température, pression), tolérances par dimension, retrait, PVT/matière, sensibilités et catégorie de variation (contrôlée, bruit ou incertitude de modèle). L'exemple optimise simultanément coût d'outillage/tolérances et réglages de procédé pour une charnière en polypropylène ; il donne notamment des plages illustratives de température et pression, pas des seuils généraux de production.

### Limites

L'exemple est analytique, fondé sur des données PVT et un modèle empirique de polypropylène. Les intervalles de possibilité ne sont pas des distributions statistiques et ne remplacent pas des répétitions de production ou une validation métrologique. Le coût, les constantes et les tolérances de l'exemple ne sont pas transférables sans calibration. Le texte indique aussi que les variations pourraient être mieux modélisées par des variables stochastiques dans certains cas. Ce document traite les tolérances et le retrait, pas la consommation énergétique.

## Consigne d'intégration

Ces documents peuvent guider le schéma de variables et les contrôles de cohérence (unités, frontières système, consigne versus mesure, intervalle versus distribution). Ils ne doivent pas être utilisés comme vérité terrain, comme preuve de conformité d'une pièce, ni comme seuils IDDRV sans validation expérimentale et traçabilité de la source.
