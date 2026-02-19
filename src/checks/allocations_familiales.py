"""
Check Allocations Familiales : Taux Plein vs Réduit.

Règle (2026):
- Si Brut < 3.5 SMIC : Taux = 3.45% (Réduit)
- Si Brut >= 3.5 SMIC : Taux = 5.25% (Plein = 3.45% base + 1.80% complément)

ATTENTION - Subtilité des logiciels de paie:
Certains logiciels (comme CEGI) affichent systématiquement les cotisations à taux plein
en haut du bulletin, puis appliquent la réduction via l'allègement RGDU en bas.
Dans ce cas, la présence de la ligne 20700 (supplément 1.80%) avec un salaire < 3.5 SMIC
est valide SI une ligne d'allègement RGDU existe.
"""

from decimal import Decimal

from src.models.payslip import FichePayeExtracted
from src.models.check import CheckResult


# Numéros de lignes standards
LIGNE_ALLOC_FAM = "20400"
LIGNE_ALLOC_FAM_SUP = "20700"

# Lignes d'allègement RGDU (Réduction Générale)
LIGNES_ALLEGEMENT_RGDU = [
    "73576",  # Allègement RGDU
    "73500",  # Réduction générale
    "73570",  # RGDU
    "73575",  # Allègement général
]

# Patterns pour détecter l'allègement RGDU par libellé
PATTERNS_ALLEGEMENT_RGDU = [
    "allègement rgdu",
    "allegement rgdu",
    "réduction générale",
    "reduction generale",
    "rgdu",
    "allègement cotisations",
    "allegement cotisations",
]

# Taux
TAUX_REDUIT = Decimal("3.45")
TAUX_SUPPLEMENT = Decimal("1.80")
TAUX_PLEIN = TAUX_REDUIT + TAUX_SUPPLEMENT  # 5.25%

# Seuil
SEUIL_SMIC_MULTIPLE = Decimal("3.5")

TOLERANCE = Decimal("0.01")  # Tolérance sur les taux


def _has_allegement_rgdu(fiche: FichePayeExtracted) -> bool:
    """
    Vérifie si la fiche contient une ligne d'allègement RGDU.

    L'allègement RGDU est un "fourre-tout" négatif qui récupère les surtaxes
    (allocations familiales 1.80%, maladie 6%, etc.) pour les salaires < 3.5 SMIC.
    """
    for numero, ligne in fiche.lignes.items():
        # Vérifier par numéro de ligne connu
        if numero in LIGNES_ALLEGEMENT_RGDU:
            # L'allègement doit avoir un montant patronal négatif
            if ligne.montant_patronal and ligne.montant_patronal < 0:
                return True

        # Vérifier par pattern dans le libellé
        libelle_lower = ligne.libelle.lower()
        for pattern in PATTERNS_ALLEGEMENT_RGDU:
            if pattern in libelle_lower:
                # L'allègement doit avoir un montant patronal négatif
                if ligne.montant_patronal and ligne.montant_patronal < 0:
                    return True
                break

    return False


def check_allocations_familiales(
    fiche: FichePayeExtracted,
    smic_mensuel: float,
) -> CheckResult:
    """
    Vérifie la cohérence des taux d'allocations familiales.

    - Si Brut < 3.5 SMIC : Taux réduit (3.45%), pas de supplément
    - Si Brut >= 3.5 SMIC : Taux plein (3.45% + 1.80%)

    Note: Si la ligne supplément est présente mais qu'un allègement RGDU existe,
    la présentation est considérée comme valide (la réduction est appliquée globalement).

    Args:
        fiche: Fiche de paie extraite.
        smic_mensuel: SMIC mensuel en vigueur.

    Returns:
        CheckResult avec le résultat de la vérification.
    """
    # Récupérer le brut
    brut = fiche.totaux.salaire_brut
    if brut is None:
        return CheckResult(
            test_name="allocations_familiales",
            valid=False,
            is_line_error=False,
            line_number=None,
            obtained_value=None,
            expected_value=None,
            difference=None,
            message="Impossible de vérifier les allocations familiales: salaire brut non trouvé.",
        )

    # Calculer le seuil 3.5 SMIC
    smic = Decimal(str(smic_mensuel))
    seuil = smic * SEUIL_SMIC_MULTIPLE
    depasse_seuil = brut >= seuil

    # Récupérer la ligne allocations familiales de base
    ligne_base = fiche.lignes.get(LIGNE_ALLOC_FAM)
    taux_base_obtenu: Decimal | None = None
    if ligne_base and ligne_base.taux_patronal:
        taux_base_obtenu = ligne_base.taux_patronal

    # Récupérer la ligne supplément (si existe)
    ligne_sup = fiche.lignes.get(LIGNE_ALLOC_FAM_SUP)
    taux_sup_obtenu: Decimal | None = None
    has_supplement = ligne_sup is not None
    if ligne_sup and ligne_sup.taux_patronal:
        taux_sup_obtenu = ligne_sup.taux_patronal

    # Vérifier si un allègement RGDU existe
    has_rgdu = _has_allegement_rgdu(fiche)

    # Vérification
    if depasse_seuil:
        # Doit avoir le supplément
        if not has_supplement:
            return CheckResult(
                test_name="allocations_familiales",
                valid=False,
                is_line_error=True,
                line_number=LIGNE_ALLOC_FAM_SUP,
                obtained_value=None,
                expected_value=TAUX_SUPPLEMENT,
                difference=None,
                message=(
                    f"Brut ({brut}€) >= 3.5 SMIC ({seuil}€): "
                    f"le supplément allocations familiales ({TAUX_SUPPLEMENT}%) devrait être appliqué. "
                    f"Ligne {LIGNE_ALLOC_FAM_SUP} non trouvée."
                ),
            )

        # Vérifier le taux du supplément
        if taux_sup_obtenu is not None and abs(taux_sup_obtenu - TAUX_SUPPLEMENT) > TOLERANCE:
            return CheckResult(
                test_name="allocations_familiales",
                valid=False,
                is_line_error=True,
                line_number=LIGNE_ALLOC_FAM_SUP,
                obtained_value=taux_sup_obtenu,
                expected_value=TAUX_SUPPLEMENT,
                difference=taux_sup_obtenu - TAUX_SUPPLEMENT,
                message=(
                    f"Brut ({brut}€) >= 3.5 SMIC ({seuil}€): "
                    f"taux supplément attendu {TAUX_SUPPLEMENT}%, obtenu {taux_sup_obtenu}%."
                ),
            )

        # Tout est OK avec taux plein
        return CheckResult(
            test_name="allocations_familiales",
            valid=True,
            is_line_error=False,
            line_number=None,
            obtained_value=taux_sup_obtenu,
            expected_value=TAUX_SUPPLEMENT,
            difference=Decimal("0") if taux_sup_obtenu else None,
            message=(
                f"Brut ({brut}€) >= 3.5 SMIC ({seuil}€): "
                f"taux plein correctement appliqué (base {taux_base_obtenu}% + supplément {taux_sup_obtenu}%)."
            ),
        )

    else:
        # Brut < 3.5 SMIC : ne devrait PAS avoir le supplément
        # MAIS si un allègement RGDU existe, la présentation est valide
        if has_supplement and taux_sup_obtenu and taux_sup_obtenu > 0:
            if has_rgdu:
                # La surtaxe est présente mais sera compensée par l'allègement RGDU
                return CheckResult(
                    test_name="allocations_familiales",
                    valid=True,
                    is_line_error=False,
                    line_number=None,
                    obtained_value=taux_sup_obtenu,
                    expected_value=TAUX_REDUIT,
                    difference=None,
                    message=(
                        f"Brut ({brut}€) < 3.5 SMIC ({seuil}€): "
                        f"supplément {taux_sup_obtenu}% affiché sur ligne {LIGNE_ALLOC_FAM_SUP}, "
                        f"mais compensé par l'allègement RGDU. Présentation valide."
                    ),
                )
            else:
                # Pas d'allègement RGDU → la surtaxe est une vraie erreur
                return CheckResult(
                    test_name="allocations_familiales",
                    valid=False,
                    is_line_error=True,
                    line_number=LIGNE_ALLOC_FAM_SUP,
                    obtained_value=taux_sup_obtenu,
                    expected_value=Decimal("0"),
                    difference=taux_sup_obtenu,
                    message=(
                        f"Brut ({brut}€) < 3.5 SMIC ({seuil}€): "
                        f"le supplément allocations familiales ne devrait PAS être appliqué. "
                        f"Surtaxe employeur de {taux_sup_obtenu}% détectée sur ligne {LIGNE_ALLOC_FAM_SUP} "
                        f"et aucun allègement RGDU pour compenser."
                    ),
                )

        # Tout est OK avec taux réduit
        return CheckResult(
            test_name="allocations_familiales",
            valid=True,
            is_line_error=False,
            line_number=None,
            obtained_value=taux_base_obtenu,
            expected_value=TAUX_REDUIT,
            difference=Decimal("0") if taux_base_obtenu else None,
            message=(
                f"Brut ({brut}€) < 3.5 SMIC ({seuil}€): "
                f"taux réduit correctement appliqué ({taux_base_obtenu}%), pas de supplément."
            ),
        )
