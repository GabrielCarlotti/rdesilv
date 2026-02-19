"""
Vérification des bases de cotisations.

Règles:
- T1/TA/A: MIN(plafond_proratisé, brut)
- T2 Retraite: MAX(0, MIN(brut, 8×plafond) - plafond)
- TB/T2 Prévoyance: MAX(0, MIN(brut, 4×plafond) - plafond)
- APEC Global: MIN(brut, 4×plafond)
- APEC T1: MIN(plafond, brut) - même règle que T1
- APEC T2: MAX(0, MIN(brut, 4×plafond) - plafond)

IMPORTANT: La détection T1/T2 est PRIORITAIRE sur APEC.
Si une ligne contient "APEC T1", c'est la règle T1 qui s'applique, pas la règle APEC globale.
"""

import re
from decimal import Decimal

from src.models.payslip import FichePayeExtracted
from src.models.check import CheckResult


# Patterns pour identifier les tranches
# Note: On utilise (?:\b|_|\s) après T1/T2 pour gérer les variantes T1_1, T2 1, etc.
PATTERNS_T1 = [
    r"\bT1(?:\b|_|\s)",  # T1, T1_1, T1 1, etc.
    r"\bTA\b",
    r"\btranche\s*1\b",
    r"\btranche\s*A\b",
    r"\bsur\s+T1(?:\b|_|\s)",
    r"\bsur\s+TA\b",
]

PATTERNS_T2 = [
    r"\bT2(?:\b|_|\s)",  # T2, T2_1, T2 1, etc.
    r"\bTB\b",
    r"\btranche\s*2\b",
    r"\btranche\s*B\b",
    r"\bsur\s+T2(?:\b|_|\s)",
    r"\bsur\s+TB\b",
]

PATTERNS_APEC = [
    r"\bAPEC\b",
]

PATTERNS_PREVOYANCE = [
    r"\bprév",
    r"\bmut",
    r"\bsanté",
]

HEURES_TEMPS_PLEIN = Decimal("151.67")
TOLERANCE = Decimal("0.50")  # Tolérance de 50 centimes pour les arrondis


def _match_pattern(libelle: str, patterns: list[str]) -> bool:
    """Vérifie si le libellé correspond à un des patterns."""
    for pattern in patterns:
        if re.search(pattern, libelle, re.IGNORECASE):
            return True
    return False


def _get_tranche_type(libelle: str) -> str | None:
    """
    Détermine le type de tranche à partir du libellé.

    IMPORTANT: La détection T1/T2 est PRIORITAIRE.
    - "APEC T1 Cadre" → t1 (pas apec_global)
    - "APEC T2 Cadre" → apec_t2 (règle spéciale APEC jusqu'à 4 plafonds)
    - "APEC Cadre" (sans T1/T2) → apec_global
    """
    is_apec = _match_pattern(libelle, PATTERNS_APEC)
    is_t1 = _match_pattern(libelle, PATTERNS_T1)
    is_t2 = _match_pattern(libelle, PATTERNS_T2)
    is_prevoyance = _match_pattern(libelle, PATTERNS_PREVOYANCE)

    # Cas APEC avec split T1/T2
    if is_apec:
        if is_t1:
            return "t1"  # APEC T1 → règle T1 classique
        if is_t2:
            return "apec_t2"  # APEC T2 → règle spéciale (4 plafonds max)
        # APEC sans T1/T2 → règle globale
        return "apec_global"

    # T1/TA classique (prioritaire)
    if is_t1:
        return "t1"

    # T2 avec distinction prévoyance vs retraite
    if is_t2:
        if is_prevoyance:
            return "t2_prevoyance"  # TB → 4 plafonds max
        return "t2_retraite"  # T2 retraite → 8 plafonds max

    return None


def _calculer_base_attendue(
    tranche_type: str,
    brut: Decimal,
    plafond_proratise: Decimal,
) -> Decimal:
    """Calcule la base attendue selon le type de tranche."""
    if tranche_type == "t1":
        # T1/TA (et APEC T1): MIN(plafond_proratisé, brut)
        return min(plafond_proratise, brut)

    elif tranche_type == "t2_retraite":
        # T2 Retraite: MAX(0, MIN(brut, 8×plafond) - plafond)
        plafond_8x = plafond_proratise * 8
        return max(Decimal("0"), min(brut, plafond_8x) - plafond_proratise)

    elif tranche_type == "t2_prevoyance":
        # TB/T2 Prévoyance: MAX(0, MIN(brut, 4×plafond) - plafond)
        plafond_4x = plafond_proratise * 4
        return max(Decimal("0"), min(brut, plafond_4x) - plafond_proratise)

    elif tranche_type == "apec_t2":
        # APEC T2: MAX(0, MIN(brut, 4×plafond) - plafond)
        # Même règle que t2_prevoyance (4 plafonds max pour APEC)
        plafond_4x = plafond_proratise * 4
        return max(Decimal("0"), min(brut, plafond_4x) - plafond_proratise)

    elif tranche_type == "apec_global":
        # APEC Global (sans split T1/T2): MIN(brut, 4×plafond)
        plafond_4x = plafond_proratise * 4
        return min(brut, plafond_4x)

    return Decimal("0")


def check_bases(
    fiche: FichePayeExtracted,
    plafond_ss: float,
) -> list[CheckResult]:
    """
    Vérifie les bases de cotisations d'une fiche de paie.

    Args:
        fiche: Fiche de paie extraite.
        plafond_ss: Plafond de la Sécurité Sociale mensuel (ex: 4005).

    Returns:
        Liste de CheckResult pour chaque ligne vérifiée.
    """
    results: list[CheckResult] = []

    # Récupérer le brut
    brut = fiche.totaux.salaire_brut
    if brut is None:
        results.append(CheckResult(
            test_name="bases",
            valid=False,
            is_line_error=False,
            line_number=None,
            obtained_value=None,
            expected_value=None,
            difference=None,
            message="Impossible de vérifier les bases: salaire brut non trouvé.",
        ))
        return results

    # Récupérer les heures pour proratiser le plafond
    heures = fiche.totaux.cumul_heures
    if heures is None or heures == 0:
        heures = HEURES_TEMPS_PLEIN

    # Proratiser le plafond
    plafond_decimal = Decimal(str(plafond_ss))
    ratio_heures = heures / HEURES_TEMPS_PLEIN
    plafond_proratise = (plafond_decimal * ratio_heures).quantize(Decimal("0.01"))

    # Parcourir toutes les lignes
    for numero, ligne in fiche.lignes.items():
        tranche_type = _get_tranche_type(ligne.libelle)

        if tranche_type is None:
            # Pas une ligne de tranche, on skip
            continue

        # Vérifier si la base est renseignée
        if ligne.base is None:
            results.append(CheckResult(
                test_name="bases",
                valid=False,
                is_line_error=True,
                line_number=numero,
                obtained_value=None,
                expected_value=None,
                difference=None,
                message=f"Ligne {numero} ({ligne.libelle}): base non renseignée alors qu'une valeur était attendue.",
            ))
            continue

        # Calculer la base attendue
        base_attendue = _calculer_base_attendue(tranche_type, brut, plafond_proratise)
        difference = ligne.base - base_attendue
        valid = abs(difference) <= TOLERANCE

        # Variables pour la gestion des bases fractionnées (cas Apprenti)
        is_split = False
        complement_line = ""
        complement_base = Decimal("0")

        # Gestion des bases fractionnées (cas de l'Apprenti)
        # Si la base est inférieure à l'attendu, chercher une ligne complémentaire du même type
        if not valid and ligne.base < base_attendue:
            for other_num, other_line in fiche.lignes.items():
                if other_num == numero:
                    continue
                # Vérifier si c'est le même type de tranche
                if _get_tranche_type(other_line.libelle) != tranche_type:
                    continue
                if other_line.base is None:
                    continue
                # Vérifier si la somme des deux bases correspond à l'attendu
                somme_bases = ligne.base + other_line.base
                if abs(somme_bases - base_attendue) <= TOLERANCE:
                    valid = True
                    is_split = True
                    difference = Decimal("0")
                    complement_line = other_num
                    complement_base = other_line.base
                    break

        # Construire le message explicatif
        if is_split:
            formule = (
                f"Base fractionnée validée : {ligne.base}€ + {complement_base}€ "
                f"(ligne {complement_line}) = {base_attendue}€"
            )
        elif tranche_type == "t1":
            formule = f"MIN(plafond_proratisé={plafond_proratise}€, brut={brut}€)"
        elif tranche_type == "t2_retraite":
            formule = f"MAX(0, MIN(brut={brut}€, 8×plafond={plafond_proratise*8}€) - plafond={plafond_proratise}€)"
        elif tranche_type == "t2_prevoyance":
            formule = f"MAX(0, MIN(brut={brut}€, 4×plafond={plafond_proratise*4}€) - plafond={plafond_proratise}€)"
        elif tranche_type == "apec_t2":
            formule = f"APEC T2: MAX(0, MIN(brut={brut}€, 4×plafond={plafond_proratise*4}€) - plafond={plafond_proratise}€)"
        elif tranche_type == "apec_global":
            formule = f"APEC Global: MIN(brut={brut}€, 4×plafond={plafond_proratise*4}€)"
        else:
            formule = "formule inconnue"

        message = (
            f"Ligne {numero} ({ligne.libelle}): "
            f"type={tranche_type}, heures={heures}h, plafond_proratisé={plafond_proratise}€. "
            f"Formule: {formule} = {base_attendue}€. "
            f"Valeur sur fiche: {ligne.base}€. "
            f"Écart: {difference}€."
        )

        results.append(CheckResult(
            test_name="bases",
            valid=valid,
            is_line_error=True,
            line_number=numero,
            obtained_value=ligne.base,
            expected_value=base_attendue,
            difference=difference,
            message=message,
        ))

    # Si aucune ligne de tranche trouvée, le signaler
    if not results:
        results.append(CheckResult(
            test_name="bases",
            valid=True,
            is_line_error=False,
            line_number=None,
            obtained_value=None,
            expected_value=None,
            difference=None,
            message="Aucune ligne de tranche (T1/T2/TA/TB/APEC) trouvée à vérifier.",
        ))

    return results
