"""
Check CSG : Reconstruction de la Base CSG/CRDS.

Règle:
Base CSG = (Salaire Brut × 98.25%) + Part Patronale Mutuelle + Part Patronale Prévoyance
"""

import re
from decimal import Decimal

from src.models.payslip import FichePayeExtracted
from src.models.check import CheckResult


# Numéros de lignes standards
LIGNE_CSG_DEDUCTIBLE = "73000"
LIGNE_MUTUELLE = "58000"
LIGNE_MALADIE_NON_RESIDENT = "20065"

# Patterns pour détecter les non-résidents fiscaux
PATTERNS_NON_RESIDENT = [
    "non résident",
    "non resident",
    "non-résident",
    "non-resident",
]

# Patterns pour détecter les apprentis (exonérés de CSG/CRDS)
PATTERNS_APPRENTI = [
    "apprenti",
    "app exo",
    "appr non exo",
    "base apprenti",
]

# Taux d'abattement pour frais professionnels
TAUX_ABATTEMENT = Decimal("0.9825")  # 98.25%

TOLERANCE = Decimal("0.50")


def _est_ligne_prevoyance(libelle: str) -> bool:
    """Détecte si une ligne est une ligne de prévoyance."""
    patterns = [
        r"\bprévo",
        r"\bprevo",
        r"\bprevoyance",
        r"\bdécès",
        r"\binvalidité",
        r"\bincapacité",
    ]
    for pattern in patterns:
        if re.search(pattern, libelle, re.IGNORECASE):
            return True
    return False


def _is_non_resident(fiche: FichePayeExtracted) -> bool:
    """Détecte si le salarié est non-résident fiscal français."""
    # Vérifier par numéro de ligne connu
    if LIGNE_MALADIE_NON_RESIDENT in fiche.lignes:
        return True

    # Vérifier par pattern dans les libellés
    for ligne in fiche.lignes.values():
        libelle_lower = ligne.libelle.lower()
        for pattern in PATTERNS_NON_RESIDENT:
            if pattern in libelle_lower:
                return True

    return False


def _is_apprenti(fiche: FichePayeExtracted) -> bool:
    """Détecte si le salarié est un apprenti (exonéré de CSG/CRDS)."""
    # Vérifier par pattern dans les libellés des lignes
    for ligne in fiche.lignes.values():
        libelle_lower = ligne.libelle.lower()
        if any(pattern in libelle_lower for pattern in PATTERNS_APPRENTI):
            return True

    # Vérifier dans l'emploi/qualification si disponible
    if fiche.employe.emploi and "apprenti" in fiche.employe.emploi.lower():
        return True
    if fiche.employe.qualification and "apprenti" in fiche.employe.qualification.lower():
        return True

    return False


def check_csg(fiche: FichePayeExtracted) -> CheckResult:
    """
    Vérifie la cohérence de la base CSG.

    Base CSG = (Brut × 98.25%) + Part Patronale Mutuelle + Part Patronale Prévoyance

    Note: Les salariés non-résidents fiscaux français sont exonérés de CSG/CRDS.

    Args:
        fiche: Fiche de paie extraite.

    Returns:
        CheckResult avec le résultat de la vérification.
    """
    # Vérifier si le salarié est non-résident fiscal (exonéré de CSG/CRDS)
    if _is_non_resident(fiche):
        return CheckResult(
            test_name="csg",
            valid=True,
            is_line_error=False,
            line_number=None,
            obtained_value=None,
            expected_value=None,
            difference=None,
            message="Salarié non-résident fiscal français. Exonéré de CSG/CRDS.",
        )

    # Vérifier si le salarié est apprenti (exonéré totalement de CSG/CRDS)
    if _is_apprenti(fiche):
        return CheckResult(
            test_name="csg",
            valid=True,
            is_line_error=False,
            line_number=None,
            obtained_value=None,
            expected_value=None,
            difference=None,
            message="Salarié apprenti détecté. Exonéré totalement de CSG/CRDS.",
        )

    # Récupérer la base CSG déclarée (depuis la ligne CSG déductible)
    base_csg_declaree: Decimal | None = None
    ligne_csg = fiche.lignes.get(LIGNE_CSG_DEDUCTIBLE)
    if ligne_csg and ligne_csg.base:
        base_csg_declaree = ligne_csg.base

    if base_csg_declaree is None:
        return CheckResult(
            test_name="csg",
            valid=False,
            is_line_error=True,
            line_number=LIGNE_CSG_DEDUCTIBLE,
            obtained_value=None,
            expected_value=None,
            difference=None,
            message=f"Impossible de vérifier la base CSG: ligne {LIGNE_CSG_DEDUCTIBLE} non trouvée ou base non renseignée.",
        )

    # Récupérer le brut
    brut = fiche.totaux.salaire_brut
    if brut is None:
        return CheckResult(
            test_name="csg",
            valid=False,
            is_line_error=False,
            line_number=None,
            obtained_value=base_csg_declaree,
            expected_value=None,
            difference=None,
            message="Impossible de vérifier la base CSG: salaire brut non trouvé.",
        )

    # Calculer l'abattement sur le brut
    brut_abattu = (brut * TAUX_ABATTEMENT).quantize(Decimal("0.01"))

    # Récupérer part patronale mutuelle
    mutuelle_pat = Decimal("0")
    ligne_mut = fiche.lignes.get(LIGNE_MUTUELLE)
    if ligne_mut and ligne_mut.montant_patronal:
        mutuelle_pat = abs(ligne_mut.montant_patronal)

    # Récupérer parts patronales prévoyance (toutes les lignes)
    prevoyance_pat = Decimal("0")
    lignes_prevoyance = []
    for numero, ligne in fiche.lignes.items():
        if _est_ligne_prevoyance(ligne.libelle) and ligne.montant_patronal:
            montant = abs(ligne.montant_patronal)
            prevoyance_pat += montant
            lignes_prevoyance.append(f"{numero}:{montant}€")

    # Calculer la base CSG attendue
    base_csg_calculee = brut_abattu + mutuelle_pat + prevoyance_pat

    difference = base_csg_declaree - base_csg_calculee
    valid = abs(difference) <= TOLERANCE

    prevoyance_detail = ", ".join(lignes_prevoyance) if lignes_prevoyance else "aucune"

    message = (
        f"Base CSG = Brut ({brut}€) × 98.25% ({brut_abattu}€) "
        f"+ Mutuelle Patronale ({mutuelle_pat}€) "
        f"+ Prévoyance Patronale ({prevoyance_pat}€ [{prevoyance_detail}]) "
        f"= {base_csg_calculee}€. "
        f"Valeur déclarée: {base_csg_declaree}€. "
        f"Écart: {difference}€."
    )

    return CheckResult(
        test_name="csg",
        valid=valid,
        is_line_error=True,
        line_number=LIGNE_CSG_DEDUCTIBLE,
        obtained_value=base_csg_declaree,
        expected_value=base_csg_calculee,
        difference=difference,
        message=message,
    )
