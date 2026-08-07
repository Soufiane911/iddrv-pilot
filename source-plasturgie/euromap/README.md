# Sources publiques — EUROMAP et données de machines

Date de consultation : **2026-08-03**.

Ce dossier contient deux paquets de publication officiels EUROMAP, téléchargés
depuis `euromap.org`, ainsi que leur contenu extrait sans modification. Les
PDF portent une signature `%PDF-` et ont été contrôlés avec `file` et
`pypdf` ; aucun fichier téléchargé n'est une page HTML renommée.

## Sources téléchargées

### EUROMAP 77 — Release 1.01

- **Titre :** *OPC UA interfaces for plastics and rubber machinery – Data
  exchange between injection moulding machines and MES*.
- **Organisme/auteur :** EUROMAP Technical Commission, c/o VDMA ; le PDF
  indique Barbara Müllers comme auteur de fichier. La publication est
  identique à OPC 40077 Release 1.01 et VDMA 40077:2020-06.
- **URL de la page officielle :**
  https://www.euromap.org/euromap77
- **URL de téléchargement consultée :**
  https://www.euromap.org/media/recommendations/77/2020/EUROMAP77_Release_1.01.zip
- **Statut d'usage :** publication publique. L'« Agreement of Use » OPC
  Foundation/EUROMAP indique que l'usage est gratuit et autorise la
  distribution, l'impression et la copie si le contenu reste inchangé ; il
  interdit notamment la vente/licence du document et l'usage publicitaire.
  Référence de ces conditions :
  https://reference.opcfoundation.org/specs/OPC-40077/agreement-of-use
- **Contenu utile pour l'injection plastique :** interface IMM–MES ;
  identification et état de la machine, configuration, moules, unités
  d'injection et unités de puissance, utilisateurs et événements, gestion des
  jobs, compteurs/cycles, paramètres de cycle, qualité et transfert/gestion des
  jeux de production. Le NodeSet XML et `NodeIds.csv` rendent le modèle
  exploitable par un serveur ou un client OPC UA.
- **Fichiers conservés :**
  `EUROMAP77_Release_1.01.zip` et le répertoire
  `EUROMAP77_Release_1.01/` (PDF, XML, CSV).
- **Limites :** Release 1.01 datée du 2020-06-01 ; ce n'est pas une
  spécification de commande directe des mouvements ni une spécification de
  sécurité machine. Les conditions de l'accord restent applicables ; ne pas
  modifier ni présenter le document comme une certification.
- **Consultation OPC Foundation :**
  https://reference.opcfoundation.org/specs/OPC-40077

### EUROMAP 83 — Release 1.03

- **Titre :** *OPC UA for Plastics and Rubber Machinery – General Type
  Definitions*.
- **Organisme/auteur :** EUROMAP Technical Commission, c/o VDMA ; le PDF
  indique Barbara Müllers comme auteur de fichier. La publication est
  identique à OPC 40083 Release 1.03 et VDMA 40083:2021-08.
- **URL de la page officielle :**
  https://www.euromap.org/euromap83
- **URL de téléchargement consultée :**
  https://www.euromap.org/media/recommendations/83/2021/EUROMAP83_Release_1.03.zip
- **Statut d'usage :** publication publique. L'« Agreement of Use » OPC
  Foundation/EUROMAP autorise gratuitement la distribution, l'impression et
  la copie du document inchangé, avec les restrictions indiquées ci-dessus.
  Référence :
  https://reference.opcfoundation.org/specs/OPC-40083/agreement-of-use
- **Contenu utile pour l'injection plastique :** types généraux réutilisables
  par les modèles de machines : identification, configuration et état,
  journaux, utilisateurs, moules, unités de puissance, zones de température,
  jobs et compteurs, paramètres surveillés/commandés, maintenance, matériaux,
  énergie, appareils de mesure, entraînements et diagnostics. EUROMAP 83 est la
  base commune réutilisée par EUROMAP 77 et d'autres Companion Specifications.
- **Fichiers conservés :**
  `EUROMAP83_Release_1.03.zip` et le répertoire
  `EUROMAP83_Release_1.03/` (PDF, XML, BSD, XSD, CSV).
- **Limites :** types généraux, pas une interface MES complète à lui seul ;
  Release 1.03 datée du 2021-06-01. Les implémentations doivent aussi gérer
  les modèles OPC UA requis et les conditions de l'accord d'usage.
- **Consultation OPC Foundation :**
  https://reference.opcfoundation.org/specs/OPC-40083

## Fiches URL uniquement (pas de copie)

### EUROMAP 102 — Technical Data for Injection Moulding Machines

- **Titre :** *EUROMAP 102 — Technical Data for Injection Moulding Machines*,
  modèle de sous-modèle Asset Administration Shell.
- **Organisme/auteur :** EUROMAP ; l'auteur individuel n'est pas indiqué sur
  la page. La page mentionne une base issue du projet de recherche
  « interOpera ».
- **URL de consultation :** https://www.euromap.org/euromap102
- **PDF public indiqué par la page :**
  https://www.euromap.org/media/recommendations/102/Draft%201.0/EUROMAP%20102%20Draft%201.0.pdf
- **Statut d'usage :** brouillon 1.0 publié le 2026-01-16. La page ne fournit
  pas de licence claire autorisant la redistribution du PDF ; il est donc
  référencé seulement par URL, conformément à la règle de non-copie des PDF
  sous copyright consultables publiquement.
- **Contenu utile :** propriétés techniques destinées à décrire une machine
  d'injection ; pertinent pour un catalogue de caractéristiques, un jumeau
  numérique/AAS et l'interopérabilité des données machine.
- **Limites :** brouillon, non une version finale ; la page annonçait une
  période de commentaires jusqu'au 2026-04-17. La conformité, la stabilité du
  modèle et les droits de redistribution doivent être vérifiés avant usage.

## Contrôle des fichiers

Les archives ZIP sont les téléchargements originaux ; leur contenu a été
extrait avec `unzip` sans transformation. `unzip -t` est OK pour les deux
archives. Les tailles et empreintes SHA-256 finales sont listées ci-dessous
pour rendre le contrôle reproductible.

| Fichier | Taille | Type vérifié |
|---|---:|---|
| `EUROMAP77_Release_1.01.zip` | 490 736 octets | ZIP, `unzip -t` OK |
| `EUROMAP77_Release_1.01/EUROMAP77_Release_1.01.pdf` | 567 594 octets | PDF 1.7, 21 pages |
| `EUROMAP77_Release_1.01/NodeIds.csv` | 24 842 octets | CSV texte |
| `EUROMAP77_Release_1.01/Opc.Ua.PlasticsRubber.IMM2MES.NodeSet2.xml` | 305 518 octets | XML 1.0 |
| `EUROMAP83_Release_1.03.zip` | 1 406 431 octets | ZIP, `unzip -t` OK |
| `EUROMAP83_Release_1.03/EUROMAP83_Release_1.03.pdf` | 1 776 898 octets | PDF 1.7, 95 pages |
| `EUROMAP83_Release_1.03/NodeIds.csv` | 54 325 octets | CSV texte |
| `EUROMAP83_Release_1.03/Opc.Ua.PlasticsRubber.GeneralTypes.NodeSet2.bsd` | 17 615 octets | BSD/XML texte |
| `EUROMAP83_Release_1.03/Opc.Ua.PlasticsRubber.GeneralTypes.NodeSet2.xml` | 793 988 octets | XML 1.0 UTF-8 |
| `EUROMAP83_Release_1.03/Opc.Ua.PlasticsRubber.GeneralTypes.NodeSet2.xsd` | 31 452 octets | XSD/XML texte |
| `EUROMAP102_reference.md` | 925 octets | fiche Markdown, pas le PDF |

Empreintes SHA-256 des archives et des PDF :

```text
d943ef28b92f92c49a0ce33467d07ac408f4d0bbb3310ece5363af272985e1ba  EUROMAP77_Release_1.01.zip
c7a97c48e81478ee8591370e6d9abea136ef581d6ff70232fefa20df18cdfccd  EUROMAP83_Release_1.03.zip
d313e851dcc627640b2c02d7bdbc00a5c4347f97d10e53f63f6783abdcc89d1b  EUROMAP77_Release_1.01/EUROMAP77_Release_1.01.pdf
a3d1b2918b760a69db7f4943be00c0b81657e57bee5bf3c7601caf0a3b780772  EUROMAP83_Release_1.03/EUROMAP83_Release_1.03.pdf
```
