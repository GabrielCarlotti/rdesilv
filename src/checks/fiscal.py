"""
Check Fiscal : Reconstruction du Net Imposable.

Règle:
Net Imposable = Net à Payer (avant PAS) - Frais Non Imposables + CSG Non Déductible + CRDS + Part Patronale Mutuelle

Les frais non imposables comprennent :
- Remboursement transport (Navigo, etc.)
- Indemnités kilométriques
- Paniers repas
- Autres indemnités exonérées
"""

from decimal import Decimal

from src.models.payslip import FichePayeExtracted
from src.models.check import CheckResult


# Numéros de lignes standards
LIGNE_NET_AVANT_PAS = "90010"
LIGNE_CSG_NON_DEDUCTIBLE = "75050"
LIGNE_CRDS = "75060"
LIGNE_MUTUELLE = "58000"

# Lignes de frais non imposables (à soustraire du net avant PAS)
LIGNES_FRAIS_NON_IMPOSABLES = [
    "81000",  # Remboursement transport
    "81001",  # Indemnité kilométrique
    "81002",  # Panier repas
    "81010",  # Remboursement frais
    "81100",  # Indemnité transport
    "81200",  # Prime transport
]

# Patterns pour détecter les frais non imposables par libellé
PATTERNS_FRAIS_NON_IMPOSABLES = [
    "remboursement transport",
    "rembours. transport",
    "indemnité transport",
    "indem. transport",
    "frais transport",
    "navigo",
    "indemnité kilom",
    "indem. kilom",
    "panier",
    "titre restaurant",
    "ticket restaurant",
]

TOLERANCE = Decimal("0.50")


def _detect_frais_non_imposables(fiche: FichePayeExtracted) -> Decimal:
    """
    Détecte et somme les frais non imposables dans la fiche de paie.

    Ces montants gonflent le net à payer mais ne sont pas imposables.
    """
    total_frais = Decimal("0")

    for numero, ligne in fiche.lignes.items():
        # Vérifier par numéro de ligne connu
        if numero in LIGNES_FRAIS_NON_IMPOSABLES:
            if ligne.montant_salarial and ligne.montant_salarial > 0:
                total_frais += ligne.montant_salarial
            continue

        # Vérifier par pattern dans le libellé
        libelle_lower = ligne.libelle.lower()
        for pattern in PATTERNS_FRAIS_NON_IMPOSABLES:
            if pattern in libelle_lower:
                if ligne.montant_salarial and ligne.montant_salarial > 0:
                    total_frais += ligne.montant_salarial
                break

    return total_frais


def check_fiscal(fiche: FichePayeExtracted) -> CheckResult:
    """
    Vérifie la cohérence du net imposable.

    Net Imposable = Net avant PAS - Frais Non Imposables + CSG Non Déductible + CRDS + Part Patronale Mutuelle

    Les frais non imposables (remboursement transport, indemnités km, etc.)
    gonflent le net à payer mais ne sont pas imposables.

    Args:
        fiche: Fiche de paie extraite.

    Returns:
        CheckResult avec le résultat de la vérification.
    """
    # Récupérer le net imposable déclaré
    net_imposable_declare = fiche.totaux.net_imposable
    if net_imposable_declare is None:
        return CheckResult(
            test_name="fiscal",
            valid=False,
            is_line_error=False,
            line_number=None,
            obtained_value=None,
            expected_value=None,
            difference=None,
            message="Impossible de vérifier le net imposable: valeur non trouvée dans les totaux.",
        )

    # Récupérer le net avant PAS
    net_avant_pas: Decimal | None = None
    ligne_net = fiche.lignes.get(LIGNE_NET_AVANT_PAS)
    if ligne_net and ligne_net.montant_salarial:
        net_avant_pas = ligne_net.montant_salarial
    elif fiche.totaux.net_avant_impot:
        net_avant_pas = fiche.totaux.net_avant_impot

    if net_avant_pas is None:
        return CheckResult(
            test_name="fiscal",
            valid=False,
            is_line_error=False,
            line_number=None,
            obtained_value=net_imposable_declare,
            expected_value=None,
            difference=None,
            message="Impossible de vérifier le net imposable: net avant PAS non trouvé.",
        )

    # Détecter les frais non imposables
    frais_non_imposables = _detect_frais_non_imposables(fiche)

    # Récupérer CSG non déductible (valeur absolue car souvent négative)
    csg_non_ded = Decimal("0")
    ligne_csg = fiche.lignes.get(LIGNE_CSG_NON_DEDUCTIBLE)
    if ligne_csg and ligne_csg.montant_salarial:
        csg_non_ded = abs(ligne_csg.montant_salarial)

    # Récupérer CRDS (valeur absolue car souvent négative)
    crds = Decimal("0")
    ligne_crds = fiche.lignes.get(LIGNE_CRDS)
    if ligne_crds and ligne_crds.montant_salarial:
        crds = abs(ligne_crds.montant_salarial)

    # Récupérer part patronale mutuelle
    mutuelle_pat = Decimal("0")
    ligne_mut = fiche.lignes.get(LIGNE_MUTUELLE)
    if ligne_mut and ligne_mut.montant_patronal:
        mutuelle_pat = abs(ligne_mut.montant_patronal)

    # Calculer le net imposable attendu
    # Net Imposable = Net avant PAS - Frais Non Imposables + CSG ND + CRDS + Mutuelle Pat
    net_imposable_calcule = net_avant_pas - frais_non_imposables + csg_non_ded + crds + mutuelle_pat

    difference = net_imposable_declare - net_imposable_calcule
    valid = abs(difference) <= TOLERANCE

    # Construire le message
    if frais_non_imposables > 0:
        message = (
            f"Net Imposable = Net avant PAS ({net_avant_pas}€) "
            f"- Frais non imposables ({frais_non_imposables}€) "
            f"+ CSG Non Déductible ({csg_non_ded}€) "
            f"+ CRDS ({crds}€) "
            f"+ Mutuelle Patronale ({mutuelle_pat}€) "
            f"= {net_imposable_calcule}€. "
            f"Valeur déclarée: {net_imposable_declare}€. "
            f"Écart: {difference}€."
        )
    else:
        message = (
            f"Net Imposable = Net avant PAS ({net_avant_pas}€) "
            f"+ CSG Non Déductible ({csg_non_ded}€) "
            f"+ CRDS ({crds}€) "
            f"+ Mutuelle Patronale ({mutuelle_pat}€) "
            f"= {net_imposable_calcule}€. "
            f"Valeur déclarée: {net_imposable_declare}€. "
            f"Écart: {difference}€."
        )

    return CheckResult(
        test_name="fiscal",
        valid=valid,
        is_line_error=False,
        line_number=None,
        obtained_value=net_imposable_declare,
        expected_value=net_imposable_calcule,
        difference=difference,
        message=message,
    )
