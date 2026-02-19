# CEGI — Vérificateur de fiches de paie et calcul d'indemnités

Application web d'analyse automatique de bulletins de salaire et de calcul d'indemnités de licenciement ou de rupture conventionnelle.

---

## Architecture

Le projet est composé de deux dépôts distincts :

- **rdesilv-front** — interface web (React / TypeScript / Vite), servie via Nginx en production
- **rdesilv** — API REST (Python / FastAPI), packagée avec `uv` et `hatchling`

L'interface communique avec l'API via HTTP. En production Docker, les deux services sont orchestrés par un `docker-compose.yml` situé dans `rdesilv-front`.

**Stack technique :**

| Couche | Technologies |
|---|---|
| Frontend | React 18, TypeScript, Vite, Nginx |
| Backend | Python 3.12, FastAPI, uvicorn |
| IA | Google Gemini (API Generative AI) |
| Extraction PDF | PyMuPDF, pdfplumber, pdfminer-six |
| Gestion des dépendances | uv (backend), npm (frontend) |
| Conteneurisation | Docker, Docker Compose |

---

## Installation (Docker — recommandé)

Docker garantit un environnement reproductible identique quelle que soit la machine hôte. C'est la méthode à privilégier.

### Prérequis

- [Docker Desktop](https://docs.docker.com/get-docker/) installé et en cours d'exécution
- Une clé API Google Gemini ([Google AI Studio](https://aistudio.google.com/))

### 1. Cloner les deux dépôts dans un même répertoire parent

```bash
mkdir cegi && cd cegi
git clone https://github.com/GabrielCarlotti/rdesilv.git
git clone https://github.com/GabrielCarlotti/rdesilv-front.git
```

La structure doit être la suivante :

```
cegi/
├── rdesilv/          # backend
└── rdesilv-front/    # frontend
```

### 2. Créer le fichier `.env` dans le dépôt backend

Le fichier `.env` doit être placé à la racine de `rdesilv/` et respecter exactement la structure du `.env.exemple` fourni :

```bash
# rdesilv/.env
GOOGLE_API_KEY=votre_clé_api_google
GEMINI_MODEL_2_5_FLASH=gemini-2.5-flash

APP_NAME="CEGI API"
ENV=prod
HOST=0.0.0.0
PORT=8000
DEBUG=false
```

### 3. Lancer l'application

Depuis le dossier `rdesilv-front` :

```bash
cd rdesilv-front
docker compose up --build
```

La première exécution télécharge les images et compile les deux services. Les démarrages suivants sont beaucoup plus rapides.

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend | http://localhost:8000 |
| Documentation API | http://localhost:8000/docs |

Pour arrêter :

```bash
docker compose down
```

---

## Installation locale (sans Docker)

### Backend

```bash
cd rdesilv
cp .env.exemple .env   # compléter avec les vraies valeurs
uv sync
uv run dev             # serveur de développement
# ou
uv run prod            # serveur de production
```

### Frontend

```bash
cd rdesilv-front
npm install
npm run dev            # http://localhost:5173
```

Créer un fichier `.env` dans `rdesilv-front/` si l'URL du backend diffère :

```bash
VITE_API_BASE_URL=http://localhost:8000/api
```

---

## Fonctionnalités

**Onglet Analyse fiche de paie**
- Upload d'une fiche de paie PDF
- Vérification automatique des cotisations (bases, CSG, RGDU, etc.)
- Surlignage des lignes en erreur dans l'aperçu PDF
- Rapport d'erreurs groupé par type de vérification
- Export PDF du rapport

**Onglet Calcul licenciement**
- Pré-remplissage depuis les 12 dernières fiches de paie (PDF)
- Calcul de l'indemnité légale (licenciement et rupture conventionnelle)
- Support CCN 1966
- Export PDF du résultat
---

## Endpoints de l'API

La documentation interactive complète est disponible sur http://localhost:8000/docs.

---

### `POST /api/extraction`

Extrait les données structurées d'un bulletin de salaire au format PDF.

**Entrée (`multipart/form-data`) :**

| Paramètre | Type | Description |
|---|---|---|
| `file` | File | Fichier PDF de la fiche de paie |

**Sortie (`FichePayeExtracted`) :**
- Informations employeur (entreprise, SIRET, convention collective)
- Informations employé (nom, matricule, qualification, échelon)
- Période de paie
- Lignes de cotisations avec bases, taux et montants
- Totaux (brut, net imposable, net à payer)

---

### `POST /api/check`

Analyse une fiche de paie et effectue des vérifications réglementaires automatiques.

**Entrée (`multipart/form-data`) :**

| Paramètre | Type | Description |
|---|---|---|
| `file` | File | Fichier PDF de la fiche de paie |
| `smic_mensuel` | float | SMIC mensuel brut en vigueur (ex : 1823.03) |
| `effectif_50_et_plus` | bool | `true` si l'entreprise a 50 salariés ou plus |
| `plafond_ss` | float | Plafond mensuel Sécurité Sociale (ex : 3864) |
| `include_frappe_check` | bool | Active la détection de fautes de frappe via LLM |
| `include_analyse_llm` | bool | Active l'analyse de cohérence avec la convention collective via LLM |

**Vérifications effectuées :**

| Check | Description | Référence |
|---|---|---|
| RGDU | Réduction Générale des Cotisations (ex-réduction Fillon) | Art. L241-13 CSS |
| Bases T1/T2 | Tranches de cotisations (T1 <= plafond SS, T2 = excédent) | Plafond SS |
| Fiscal | Reconstruction et vérification du net imposable | CGI |
| CSG | Base CSG (98.25% du brut + cotisations patronales prévoyance/mutuelle) | CSS |
| Allocations familiales | Taux 5.25% si salaire > 3.5 SMIC, sinon taux réduit | URSSAF |
| Fautes de frappe | Détection d'erreurs typographiques via LLM (optionnel) | — |
| Convention collective | Cohérence avec la CCN 66 via LLM (optionnel) | CCN 1966 |

**Sortie (`CheckReport`) :**

```json
{
  "all_valid": true,
  "total_checks": 6,
  "passed_checks": 6,
  "failed_checks": 0,
  "checks": [
    { "test_name": "rgdu", "valid": true, "message": "..." }
  ]
}
```

---

### `POST /api/licenciement`

Calcule l'indemnité de licenciement ou de rupture conventionnelle.

**Entrée (JSON) :**

| Paramètre | Type | Description |
|---|---|---|
| `type_rupture` | enum | `licenciement` ou `rupture_conventionnelle` |
| `date_entree` | date | Date d'entrée dans l'entreprise (YYYY-MM-DD) |
| `date_notification` | date | Date de notification du licenciement (licenciement uniquement) |
| `date_fin_contrat` | date | Date de fin de contrat (fin de préavis ou date convenue) |
| `motif` | enum | Motif du licenciement (licenciement uniquement) |
| `convention_collective` | enum | `aucune` ou `ccn_1966` |
| `salaires_12_derniers_mois` | array[Decimal] | Salaires bruts des 12 derniers mois |
| `primes_annuelles_3_derniers_mois` | Decimal | Primes annuelles sur les 3 derniers mois |
| `indemnite_supralegale` | Decimal | Montant négocié supplémentaire (rupture conv. uniquement) |
| `mois_suspendus_non_comptes` | int | Mois à déduire (congé sans solde, maladie non professionnelle) |
| `mois_conge_parental_temps_plein` | int | Mois de congé parental temps plein (comptés pour 50%) |
| `age_salarie` | int | Requis pour CCN 1966 (plafond à 65 ans) |
| `salaire_mensuel_actuel` | Decimal | Requis pour CCN 1966 |

**Motifs de licenciement :**

| Valeur | Description |
|---|---|
| `personnel` | Motif personnel |
| `economique` | Motif économique |
| `inaptitude_professionnelle` | Inaptitude d'origine professionnelle (indemnité x2) |
| `inaptitude_non_professionnelle` | Inaptitude non professionnelle |
| `faute_grave` | Aucune indemnité |
| `faute_lourde` | Aucune indemnité |

**Calcul :**
1. Salaire de référence = max(moyenne 12 mois, moyenne 3 mois avec primes proratisées)
2. Indemnité légale : 1/4 mois par année jusqu'à 10 ans, 1/3 mois au-delà
3. Indemnité CCN 1966 si applicable : 1/2 mois par année, plafonnée à 6 mois
4. Principe de faveur : montant le plus élevé retenu
5. Multiplicateur x2 si inaptitude professionnelle

**Sortie (`LicenciementResult`) :**

```json
{
  "montant_indemnite": 12500.00,
  "montant_minimum": 12500.00,
  "salaire_reference": 2500.00,
  "anciennete_retenue_annees": 5.0,
  "preavis_mois": 2,
  "explication": "..."
}
```

---

### `POST /api/licenciementpdf`

Extrait les données des 12 dernières fiches de paie pour pré-remplir le formulaire de licenciement.

**Entrée (`multipart/form-data`) :**

| Paramètre | Type | Description |
|---|---|---|
| `file` | File | PDF contenant les 12 fiches de paie concaténées |

**Données extraites :** date d'entrée, convention collective détectée, salaires bruts triés par mois.

**Workflow :**
1. L'utilisateur uploade le PDF des 12 fiches
2. L'API extrait et renvoie les données
3. Le formulaire est pré-rempli automatiquement
4. L'utilisateur complète ou corrige les champs manquants
5. L'appel à `/api/licenciement` est déclenché avec les données finales

**Sortie (`LicenciementPdfExtraction`) :**

```json
{
  "extraction_success": true,
  "date_entree": "2020-01-15",
  "convention_collective": "ccn_1966",
  "convention_collective_brute": "Convention collective du 15 mars 1966",
  "salaires_12_derniers_mois": [2500, 2500, 2500],
  "salaires_extraits": [
    { "mois": 12, "annee": 2024, "salaire_brut": 2500 }
  ],
  "nombre_fiches_extraites": 12
}
```

---

## Exemples de requêtes curl

```bash
# Extraction simple
curl -X POST http://localhost:8000/api/extraction \
  -F "file=@fiche.pdf"

# Vérification complète avec analyses LLM
curl -X POST http://localhost:8000/api/check \
  -F "file=@fiche.pdf" \
  -F "smic_mensuel=1823.03" \
  -F "effectif_50_et_plus=false" \
  -F "plafond_ss=3864" \
  -F "include_frappe_check=true" \
  -F "include_analyse_llm=true"

# Calcul de licenciement économique
curl -X POST http://localhost:8000/api/licenciement \
  -H "Content-Type: application/json" \
  -d '{
    "type_rupture": "licenciement",
    "date_entree": "2020-01-15",
    "date_notification": "2025-01-01",
    "date_fin_contrat": "2025-03-01",
    "motif": "economique",
    "salaires_12_derniers_mois": [2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500]
  }'

# Rupture conventionnelle avec indemnité supralégale
curl -X POST http://localhost:8000/api/licenciement \
  -H "Content-Type: application/json" \
  -d '{
    "type_rupture": "rupture_conventionnelle",
    "date_entree": "2020-01-15",
    "date_fin_contrat": "2025-02-15",
    "salaires_12_derniers_mois": [3000, 3000, 3000, 3000, 3000, 3000, 3000, 3000, 3000, 3000, 3000, 3000],
    "indemnite_supralegale": 5000
  }'
```

---

## Pistes d'amélioration

**Couverture réglementaire**
- Étendre les vérifications à d'autres conventions collectives au-delà de la CCN 1966
- Ajouter d'autres checks réglementaires
- Mettre à jour dynamiquement les paramètres réglementaires (SMIC, plafond SS) sans redéploiement

**Extraction PDF**
- Gérer les formats multi-pages complexes et les fiches de paie scannées

**Fonctionnalités**
- Historique des analyses côté client ou via une base de données légère
- Support de plusieurs conventions collectives dans le formulaire de licenciement

**Infrastructure**
- Ajouter des tests unitaires et d'intégration (pytest côté backend, Vitest côté frontend)
- Mettre en place un pipeline CI/CD (lint, tests, build Docker)
- Ajouter un healthcheck Docker sur le backend pour synchroniser le démarrage des services

---

