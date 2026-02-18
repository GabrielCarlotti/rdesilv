"""
Check Fiscal : Reconstruction du Net Imposable.

Règle:
Net Imposable = Net à Payer (avant PAS) + CSG Non Déductible + CRDS + Part Patronale Mutuelle
"""

from decimal import Decimal

from src.models.payslip import FichePayeExtracted
from src.models.check import CheckResult


# Numéros de lignes standards
LIGNE_NET_AVANT_PAS = "90010"
LIGNE_CSG_NON_DEDUCTIBLE = "75050"
LIGNE_CRDS = "75060"
LIGNE_MUTUELLE = "58000"

TOLERANCE = Decimal("0.50")


def check_fiscal(fiche: FichePayeExtracted) -> CheckResult:
    """
    Vérifie la cohérence du net imposable.

    Net Imposable = Net avant PAS + CSG Non Déductible + CRDS + Part Patronale Mutuelle

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
    net_imposable_calcule = net_avant_pas + csg_non_ded + crds + mutuelle_pat

    difference = net_imposable_declare - net_imposable_calcule
    valid = abs(difference) <= TOLERANCE

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
