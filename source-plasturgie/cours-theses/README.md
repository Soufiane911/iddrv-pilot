# Ressources publiques — plasturgie et injection plastique

Collecte vérifiée le **3 août 2026**. Les ressources ont été recherchées dans HAL, theses.fr, des dépôts universitaires et un organisme de formation spécialisé. Aucun fichier de `data/scenarios/industrial_demo/ground_truth.json` n’a été consulté.

## Fichiers locaux

Les quatre PDF présents dans `pdfs/` proviennent de notices HAL déclarant une licence Creative Commons. Ils sont conservés avec leur licence et leur attribution :

| Fichier | Source / auteur | Année | Licence déclarée | Vérification |
|---|---|---:|---|---|
| `hal-01551840_pilotage-injection-plastique.pdf` | Pierre Nagorny, Eric Pairel, Maurice Pillet — Université Savoie Mont Blanc, laboratoire SYMME | 2017 | [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) | PDF valide, 12 pages, SHA-256 `79ea66a2674e65e272975334109d59c90ad793cc77b80306dc449ce48537b648` |
| `hal-02142331_controle-qualite-injection.pdf` | Pierre Nagorny, Maurice Pillet, Eric Pairel — Université Savoie Mont Blanc, laboratoire SYMME | 2019 | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) | PDF valide, 8 pages, SHA-256 `8ac8c1f5e7d89e0f820cb35bf876aa48e7dddfc43a3dcda37c2a61b62c223386` |
| `hal-01551797_pilotage-qualite-pieces-injectees.pdf` | Pierre Nagorny, Eric Pairel, Maurice Pillet — Université Savoie Mont Blanc, laboratoire SYMME | 2017 | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) | PDF valide, 7 pages, SHA-256 `b9141ff0a5f81daf8ce920bcacb5a6fd3f78544f53fe92dd0b4dfb1861659312` |
| `hal-01552111_quality-prediction-injection-molding.pdf` | Pierre Nagorny et al. — Université Savoie Mont Blanc, SYMME, Pôle Européen de la Plasturgie | 2017 | [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) | PDF valide, 6 pages, SHA-256 `9beed86f3c688a6b69cdcdae5de17a77b1acc30fe79c33e3e4662e9b426eb092` |

Les licences ci-dessus autorisent la mise à disposition dans leurs conditions respectives ; elles n’autorisent pas nécessairement un usage commercial. Les fichiers locaux restent des copies de la version déposée, sans modification.

## Fiches de ressources et exploitation IDDRV

Les ressources ci-dessous sont détaillées dans `sources.csv`. `fiche_url` signifie que seule la notice et l’URL sont conservées : le document est publiquement consultable, mais sa licence de réutilisation n’est pas explicite, il est marqué par HAL comme soumis à autorisation, ou il s’agit d’une page de formation. Aucun de ces PDF n’a été copié dans le dépôt.

### 1. Cycle, paramètres et pilotage — HAL `hal-01551840`

- **Source :** [notice HAL](https://hal.science/hal-01551840v1), [PDF](https://hal.science/hal-01551840/document).
- **Auteur / établissement / année :** Pierre Nagorny, Eric Pairel, Maurice Pillet ; Université Savoie Mont Blanc / SYMME ; 2017. Communication au CIGI 2017.
- **Licence / statut :** CC BY-NC-ND 4.0 déclarée dans la notice HAL ; PDF téléchargé.
- **Pages utiles :** pp. 3–4, section 3, séquencement injection–maintien–refroidissement, transition au gel du canal et temps de refroidissement ; pp. 5–6, modélisation et régulation ; pp. 7–10, pilotage, mesures et ajustement.
- **Concepts à traduire en features ML :** phase et durée de chaque étape, pression hydraulique et pression empreinte, température du fondu et du moule, position/vitesse de vis, pression de maintien, temps de refroidissement, pression maximale, gradients et dérives cycle à cycle. La pression n’est pas indépendante de la vitesse et de la température : conserver les séries temporelles et leurs alignements.

### 2. Pilotage qualité et plan d’expériences — HAL `hal-01551797`

- **Source :** [notice HAL](https://hal.science/hal-01551797v1), [PDF](https://hal.science/hal-01551797/document).
- **Auteur / établissement / année :** Pierre Nagorny, Eric Pairel, Maurice Pillet ; Université Savoie Mont Blanc / SYMME ; 2017.
- **Licence / statut :** CC BY-NC-SA 4.0 déclarée dans la notice HAL ; PDF téléchargé.
- **Pages utiles :** pp. 3–5, régulation, apprentissage et variables du procédé ; pp. 5–6, capteurs pression/température, mesure pendant le cycle et plan de criblage Plackett–Burman ; p. 6, chronogramme et limites de mesure avant éjection.
- **Concepts à traduire en features ML :** température du fourreau/fondu, pression de maintien, vitesse et pression d’injection, pression dans le moule et la buse, force de fermeture, durée d’injection et de refroidissement, masse/dimensions, signaux capteurs et leurs statistiques (maximum, moyenne, pente, aire sous la courbe). La force de fermeture et le refroidissement sont explicitement inclus dans le plan d’essais.

### 3. Contrôle qualité, dérives et défauts — HAL `hal-02142331`

- **Source :** [notice HAL](https://hal.science/hal-02142331v1), [PDF](https://hal.science/hal-02142331/document).
- **Auteur / établissement / année :** Pierre Nagorny, Maurice Pillet, Eric Pairel ; Université Savoie Mont Blanc / SYMME ; 2019. Communication CIGI-QUALITA 2019.
- **Licence / statut :** CC BY-NC-SA 4.0 déclarée dans la notice HAL ; PDF téléchargé.
- **Pages utiles :** pp. 3–5, contraintes de mesure, capteurs pression/température et mesure non invasive ; pp. 5–7, plan de criblage, construction de la base d’apprentissage et Deep Learning ; pp. 6–8, classification/validation des défauts et généralisation.
- **Concepts à traduire en features ML :** étiquette qualité experte, classe de défaut, image d’aspect, géométrie, résolution et position du capteur, pression/température dans le moule, cycle et réglages. Distinguer défauts géométriques, défauts d’aspect et dérives de procédé ; annoter le moment de mesure pour éviter une fuite de cible.

### 4. Prédiction de qualité par capteurs — HAL `hal-01552111`

- **Source :** [notice HAL](https://hal.science/hal-01552111v1), [PDF](https://hal.science/hal-01552111/document).
- **Auteur / établissement / année :** Pierre Nagorny, Maurice Pillet, Eric Pairel, Ronan Le Goff, Jerôme Loureaux, Wali Marlène, Patrice Kiener ; Université Savoie Mont Blanc / SYMME, Pôle Européen de la Plasturgie ; 2017.
- **Licence / statut :** CC BY-NC-ND 4.0 déclarée dans la notice HAL ; PDF téléchargé. Article en anglais.
- **Pages utiles :** pp. 2–3, production industrielle et instrumentation (capteur pression et température dans le moule, pression hydraulique, position de vis, cycles de 30 s) ; pp. 3–5, extraction de descripteurs, thermographie et régressions/CNN ; pp. 5–6, signaux bruts et LSTM.
- **Concepts à traduire en features ML :** séries pression/température/position à 100 Hz, statistiques et pics, coefficients de texture Haralick, thermographie à 10 s, masse et dimension comme cibles, signaux bruts pour modèles récurrents. Les acquisitions de fin de cycle ne doivent pas être utilisées si la prédiction doit précéder l’éjection.

### 5. Usure et durée de vie des inserts — thèse HAL / theses.fr `tel-03927394`

- **Source :** [notice theses.fr](https://www.theses.fr/2018LYSEE003), [notice HAL](https://theses.hal.science/tel-03927394v1), [PDF public consultable](https://theses.hal.science/tel-03927394/document).
- **Auteur / établissement / année :** Maxime Limousin ; Université de Lyon, École Centrale de Lyon, laboratoire de Tribologie et Dynamique des Systèmes ; 2018.
- **Licence / statut :** HAL indique `hal-authorisation-v1`, pas une licence Creative Commons. PDF public, mais non copié dans le dépôt.
- **Chapitres utiles :** chapitre 1, pp. 7–10, cycle, contraintes de fermeture/injection/éjection, abrasion par polymères chargés, corrosion et cycles thermiques ; annexe VI.A, p. 73, influence de la conductivité et de la distance canal–surface sur le temps de refroidissement ; chapitre 5 et annexes C–D, essais industriels et tenue à la corrosion.
- **Concepts à traduire en features ML :** compteur de cycles et âge de l’insert, grade et charge abrasive du polymère, pression/vitesse/température, humidité et qualité du fluide de refroidissement, distance canal–surface, conductivité thermique, dureté, événements de bavure, corrosion, grippage et variation dimensionnelle. La cible peut être une classe d’usure ou une durée de vie restante ; séparer les essais de matériau des données de production.

### 6. Comportement thermique des moules — HAL `hal-01798913`

- **Source :** [notice HAL](https://hal.science/hal-01798913v1), [PDF public consultable](https://hal.science/hal-01798913/document).
- **Auteur / établissement / année :** Eliette Mathey, Luc Penazzi, Fabrice Schmidt, François Ronde Oustau ; Centre de Recherche Outillages, Matériaux et Procédés / IMT Mines Albi ; 2003. Communication MECAMAT.
- **Licence / statut :** HAL indique `hal-authorisation-v1`, pas de licence Creative Commons. Fiche URL uniquement.
- **Parties utiles :** comparaison de l’assemblage des moules, champ thermique et régulation ; lecture orientée vers température de paroi, homogénéité du refroidissement et impact sur cycle/qualité.
- **Concepts à traduire en features ML :** température par zone, écart maximal entre empreintes, vitesse de refroidissement, temps pour atteindre la température d’éjection, type d’assemblage et géométrie des canaux, défauts dimensionnels et gauchissement.

### 7. Régulation thermique et canaux conformables — thèse HAL `tel-04651593`

- **Source :** [notice HAL](https://imt-mines-albi.hal.science/tel-04651593v1). La notice renvoie à la thèse de Cyril Pelaingre, soutenue en 2005 à Mines Paris–PSL / CROMeP.
- **Licence / statut :** notice HAL marquée non ouverte (`openAccess=false`) ; aucune copie de PDF.
- **Chapitres utiles selon le résumé de la notice :** conception des canaux de régulation, conductivité, durée de cycle, précision géométrique, propriétés mécaniques et réduction du temps de refroidissement.
- **Concepts à traduire en features ML :** distance et topologie des canaux, débit du fluide, température d’entrée/sortie, conductivité, gradient thermique, temps de refroidissement, tolérance dimensionnelle et propriétés mécaniques. Cette fiche complète la ressource HAL 01798913 sans supposer un accès intégral.

### 8. Support universitaire sur presse, défauts et force de fermeture — ENP `P000386`

- **Source :** [notice du dépôt ENP](https://repository.enp.edu.dz/jspui/handle/123456789/1062), [PDF public](https://repository.enp.edu.dz/jspui/bitstream/123456789/1062/1/CHERIEF.El-hadi.pdf).
- **Auteur / établissement / année :** Cherief El-Hadi ; École Nationale Polytechnique d’Alger, Département de Génie Mécanique ; 2019. Mémoire de projet de fin d’études, *Etude et conception d'un moule d'injection plastique à partir d'une pièce modèle*.
- **Licence / statut :** dépôt public, licence de réutilisation non indiquée ; fiche URL uniquement.
- **Chapitres utiles :** chapitre I, pp. 22–36 : presse, fourreau, moule, phases injection/compactage/refroidissement/éjection et défauts ; chapitre II, pp. 38–49 : fonctions, matériaux et refroidissement du moule ; chapitre V, pp. 68–76 : pression, force de fermeture/verrouillage, températures et temps de refroidissement.
- **Concepts à traduire en features ML :** pression d’injection et pression empreinte, température matière/moule/éjection, force de fermeture et marge de verrouillage, temps de remplissage/maintien/refroidissement, ventilation, retrait, bavure, manque de matière, retassure, marques d’éjecteurs, fissuration et défauts d’aspect.

### 9. Cours universitaire de conception de moules — Université Batna 2

- **Source :** [support public sur l’espace enseignant](https://staff.univ-batna2.dz/sites/default/files/mansouri_naima/files/chapitre-4-conception-moules-injection-matieres-plastiques.pdf).
- **Auteur / établissement / année :** auteur et année non indiqués dans le fichier ; support hébergé sur le site de l’Université Batna 2, espace public de Naima Mansouri. Titre : *Chapitre IV — Conception des moules d’injection des matières plastiques*.
- **Licence / statut :** PDF publiquement accessible mais droits non précisés ; fiche URL uniquement.
- **Parties utiles vérifiées :** pp. 6–7, solidification/refroidissement ; p. 14, défauts à éviter ; pp. 17–18, circuits de refroidissement ; pp. 20 et 24–25, pression, forces et dimensionnement de presse.
- **Concepts à traduire en features ML :** température de moule et de matière, débit/circuit de refroidissement, pression d’empreinte, force de fermeture, usure des éléments sollicités, défauts et maintenance du moule.

### 10. Formation professionnelle sur les défauts — FSRM

- **Source :** [page de cours FSRM](https://fsrm.ch/doc/c724.php), *Plasturgie : détecter et prévenir les défauts d’injection*.
- **Auteur / établissement / année :** FSRM ; organisme de formation suisse ; auteur et année non indiqués sur la page.
- **Licence / statut :** page de présentation d’une formation ; supports de cours non copiés, droits FSRM.
- **Contenu utile :** relation écoulement–défauts de surface, démarche de recherche des causes, défauts de surface, mécaniques et dimensionnels, exemples de pièces réelles.
- **Concepts à traduire en features ML :** taxonomie de défauts, mesures d’aspect et dimensionnelles, variables d’écoulement, paramètres de réglage, cause présumée et action corrective. Cette source est utile pour structurer les labels et la matrice cause–défaut, pas pour fournir un corpus de texte sous copyright.

## Traduction commune en schéma de données IDDRV

- **Entrées machine et matière :** température par zone du fourreau et température du fondu, température du moule, pression/vitesse d’injection, pression de maintien, contre-pression, position/vitesse de vis, dosage, force de fermeture, matériau/grade, charge fibreuse, humidité et numéro d’empreinte.
- **Séries temporelles :** horodatage de début/fin injection, commutation injection–maintien, gel du seuil, fin de maintien, dosage, refroidissement et éjection ; conserver pics, pentes, intégrales, dérivées, délais et températures par capteur plutôt que seulement des moyennes.
- **Sorties qualité :** masse, cotes, retrait, gauchissement, aspect, bavure, manque de matière, retassure, ligne de soudure, brûlure, marques d’éjecteur, fissure, classe « conforme/non conforme » et cause experte.
- **État de l’outillage :** compteur de cycles, maintenance, usure/corrosion, état des évents, colmatage et distance des canaux de régulation. Une cible de durée de vie ou de dérive doit être séparée des mesures prises après le défaut.
- **Précautions ML :** séparer les cycles par lot, matière, moule et période de production pour l’évaluation ; documenter calibration et dérive des capteurs ; éviter d’utiliser une mesure de qualité réalisée après éjection pour prédire une décision qui doit être prise avant l’éjection ; conserver l’incertitude et le lien entre défaut et action corrective.

## Contrôle effectué

Les quatre téléchargements ont été vérifiés par signature `%PDF-`, `file`, `pdfinfo` et extraction de texte `pdftotext`. Les notices HAL et les pages externes ont été consultées sans contourner de paywall. Les ressources dont le statut de réutilisation n’était pas clairement compatible avec une copie ont été conservées uniquement sous forme de fiches URL dans `sources.csv`.
