# rdesilv

API de vérification et d'analyse des fiches de paie, avec calcul d'indemnités de licenciement.

## Endpoints

### 1. `POST /extraction` - Extraction de fiche de paie

Extrait les données structurées d'un bulletin de salaire PDF.

**Entrée (multipart/form-data):**
| Paramètre | Type | Description |
|-----------|------|-------------|
| `file` | File | Fichier PDF de la fiche de paie |

**Sortie:** `FichePayeExtracted` (JSON)
- Informations employeur (entreprise, SIRET, convention collective...)
- Informations employé (nom, matricule, qualification, échelon...)
- Période de paie
- Lignes de cotisations avec bases, taux et montants
- Totaux (brut, net imposable, net à payer...)

---

### 2. `POST /check` - Vérification de fiche de paie

Analyse une fiche de paie et effectue des vérifications automatiques.

**Entrée (multipart/form-data):**
| Paramètre | Type | Description |
|-----------|------|-------------|
| `file` | File | Fichier PDF de la fiche de paie |
| `smic_mensuel` | float | SMIC mensuel brut en vigueur (ex: 1823.03) |
| `effectif_50_et_plus` | bool | `true` si l'entreprise a 50+ salariés |
| `plafond_ss` | float | Plafond mensuel Sécurité Sociale (ex: 3864) |
| `include_frappe_check` | bool | `true` pour activer la détection de fautes de frappe (LLM) |
| `include_analyse_llm` | bool | `true` pour activer l'analyse de cohérence convention collective (LLM) |

**Checks effectués:**

| Check | Description | Source |
|-------|-------------|--------|
| **RGDU** | Vérifie le calcul de la Réduction Générale des Cotisations (ex-réduction Fillon) | Code de la Sécurité Sociale, Art. L241-13 |
| **Bases T1/T2** | Vérifie les tranches de cotisations (T1 ≤ plafond SS, T2 = excédent) | Plafond SS |
| **Fiscal** | Reconstruit et vérifie le net imposable | CGI |
| **CSG** | Vérifie la base CSG (98.25% du brut + cotisations patronales prévoyance/mutuelle) | Code de la Sécurité Sociale |
| **Allocations Familiales** | Vérifie le taux (5.25% si salaire > 3.5 SMIC, sinon taux réduit) | URSSAF |
| **Fautes de frappe** | Détecte les erreurs typographiques via LLM (optionnel) | - |
| **Convention collective** | Analyse la cohérence avec la CCN 66 via LLM (optionnel) | CCN 1966 |

**Sortie:** `CheckReport` (JSON)
```json
{
  "all_valid": true,
  "total_checks": 6,
  "passed_checks": 6,
  "failed_checks": 0,
  "checks": [
    {
      "test_name": "rgdu",
      "valid": true,
      "message": "..."
    }
  ]
}
```

---

### 3. `POST /licenciement` - Calcul d'indemnité de licenciement

Calcule l'indemnité de licenciement ou de rupture conventionnelle.

**Entrée (JSON body):**

| Paramètre | Type | Description |
|-----------|------|-------------|
| `type_rupture` | enum | `licenciement` ou `rupture_conventionnelle` |
| `date_entree` | date | Date d'entrée dans l'entreprise (YYYY-MM-DD) |
| `date_notification` | date | Date de notification du licenciement (requis pour licenciement) |
| `date_fin_contrat` | date | Date de fin du contrat (fin préavis pour licenciement, date convenue pour rupture conv.) |
| `motif` | enum | Motif du licenciement (requis pour licenciement) |
| `convention_collective` | enum | `aucune` ou `ccn_1966` |
| `salaires_12_derniers_mois` | array[Decimal] | Salaires bruts des 12 derniers mois |
| `primes_annuelles_3_derniers_mois` | Decimal | Primes annuelles dans les 3 derniers mois |
| `indemnite_supralegale` | Decimal | Montant négocié en plus (rupture conv. uniquement) |
| `mois_suspendus_non_comptes` | int | Mois à déduire (congé sans solde, sabbatique, maladie non pro) |
| `mois_conge_parental_temps_plein` | int | Mois de congé parental temps plein (compte pour 50%) |
| `age_salarie` | int | Requis pour CCN 1966 (plafond 65 ans) |
| `salaire_mensuel_actuel` | Decimal | Requis pour CCN 1966 |

**Motifs de licenciement:**
- `personnel` - Licenciement pour motif personnel
- `economique` - Licenciement économique
- `inaptitude_professionnelle` - Inaptitude d'origine professionnelle (indemnité x2)
- `inaptitude_non_professionnelle` - Inaptitude non professionnelle
- `faute_grave` - Pas d'indemnité
- `faute_lourde` - Pas d'indemnité

**Calcul de l'ancienneté:**
- **Licenciement:** `date_fin_contrat - date_entree` (le préavis est inclus automatiquement)
- **Rupture conv.:** `date_fin_contrat - date_entree` (pas de préavis)

**Calculs effectués:**

1. **Préavis** (licenciement) = `date_fin_contrat - date_notification`
2. **Salaire de référence** = max(moyenne 12 mois, moyenne 3 mois avec primes proratisées)
3. **Indemnité légale:**
   - ≤ 10 ans : 1/4 mois par année
   - > 10 ans : 1/3 mois par année supplémentaire
4. **Indemnité CCN 1966** (si applicable):
   - 1/2 mois par année
   - Plafond : 6 mois de salaire
   - Plafond : rémunérations jusqu'à 65 ans
5. **Principe de faveur** : on retient le montant le plus élevé
6. **Multiplicateur x2** si inaptitude professionnelle

**Différences licenciement vs rupture conventionnelle:**
| | Licenciement | Rupture conventionnelle |
|--|--------------|------------------------|
| Motif | Requis | Aucun |
| Préavis | Calculé auto (date_fin - date_notif) | Pas de préavis |
| Supralégal | Non | Négociable |

**Sources:**
- Code du travail : L1234-9, R1234-1, R1234-2, R1234-4
- CCN 1966 : Article sur l'indemnité de licenciement

**Sortie:** `LicenciementResult` (JSON)
```json
{
  "montant_indemnite": 12500.00,
  "montant_minimum": 12500.00,
  "salaire_reference": 2500.00,
  "anciennete_retenue_annees": 5.0,
  "preavis_mois": 2,
  "explication": "Licenciement pour motif économique. Date d'entrée: 01/01/2020. Date de fin: 01/03/2025. Préavis de 2 mois. Ancienneté retenue: 5 an(s) et 2 mois. ..."
}
```

---

### 4. `POST /licenciementpdf` - Extraction depuis fiches de paie

Extrait les données des 12 dernières fiches de paie pour pré-remplir le formulaire de licenciement.

**Entrée (multipart/form-data):**
| Paramètre | Type | Description |
|-----------|------|-------------|
| `file` | File | PDF contenant les 12 fiches de paie concaténées |

**Données extraites:**
- `date_entree` - Date d'entrée dans l'entreprise
- `convention_collective` - Convention détectée automatiquement
- `salaires_12_derniers_mois` - Salaires bruts extraits et triés

**Workflow:**
1. Le frontend upload le PDF avec les 12 fiches
2. L'API extrait les données et les renvoie
3. Le frontend pré-remplit le formulaire
4. L'utilisateur complète/corrige (dates, primes, ajustements)
5. Le frontend appelle `/licenciement` avec les données finales

**Sortie:** `LicenciementPdfExtraction` (JSON)
```json
{
  "extraction_success": true,
  "date_entree": "2020-01-15",
  "convention_collective": "ccn_1966",
  "convention_collective_brute": "Convention collective du 15 mars 1966",
  "salaires_12_derniers_mois": [2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500],
  "salaires_extraits": [
    {"mois": 12, "annee": 2024, "salaire_brut": 2500},
    {"mois": 11, "annee": 2024, "salaire_brut": 2500}
  ],
  "nombre_fiches_extraites": 12
}
```

---

## Installation

```bash
# Cloner le repo
git clone <repo-url>
cd rdesilv

# Installer les dépendances
uv sync

# Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec vos clés API (GOOGLE_API_KEY pour les checks LLM)

# Lancer le serveur
uv run dev
```

## Exemples de requêtes

```bash
# Extraction simple
curl -X POST http://localhost:8000/extraction \
  -F "file=@fiche.pdf"

# Check complet avec analyses LLM
curl -X POST http://localhost:8000/check \
  -F "file=@fiche.pdf" \
  -F "smic_mensuel=1823.03" \
  -F "effectif_50_et_plus=false" \
  -F "plafond_ss=3864" \
  -F "include_frappe_check=true" \
  -F "include_analyse_llm=true"

# Extraction depuis PDF pour licenciement
curl -X POST http://localhost:8000/licenciementpdf \
  -F "file=@12_fiches_de_paie.pdf"

# Calcul licenciement
curl -X POST http://localhost:8000/licenciement \
  -H "Content-Type: application/json" \
  -d '{
    "type_rupture": "licenciement",
    "date_entree": "2020-01-15",
    "date_notification": "2025-01-01",
    "date_fin_contrat": "2025-03-01",
    "motif": "economique",
    "salaires_12_derniers_mois": [2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500, 2500]
  }'

# Rupture conventionnelle avec supralégal
curl -X POST http://localhost:8000/licenciement \
  -H "Content-Type: application/json" \
  -d '{
    "type_rupture": "rupture_conventionnelle",
    "date_entree": "2020-01-15",
    "date_fin_contrat": "2025-02-15",
    "salaires_12_derniers_mois": [3000, 3000, 3000, 3000, 3000, 3000, 3000, 3000, 3000, 3000, 3000, 3000],
    "indemnite_supralegale": 5000
  }'
```
