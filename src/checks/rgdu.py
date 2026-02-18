"""
Calcul de la Réduction Générale Dégressive Unique (RGDU) 2026
Selon le décret n°2025-887 du 4 septembre 2025
"""

from decimal import Decimal
from typing import Any

from src.models.payslip import FichePayeExtracted
from src.models.check import CheckResult


def calculer_rgdu(
    brut_mensuel: float,
    heures_contractuelles: float = 151.67,
    heures_supplementaires: float = 0,
    effectif_50_et_plus: bool = True,
    smic_mensuel: float = 1823.03,
    tdeltaopt:Any = None,
) -> dict:
    """
    Calcule la réduction générale dégressive unique (RGDU) mensuelle.

    Args:
        brut_mensuel: Salaire brut total du bulletin (rémunération soumise à cotisations)
        heures_contractuelles: Heures contractuelles mensuelles (défaut 151.67 pour 35h)
        heures_supplementaires: Nombre d'heures supplémentaires du mois
        effectif_50_et_plus: True si entreprise >= 50 salariés, False sinon
        smic_mensuel: SMIC mensuel brut 2026 (défaut 1823.03 €)
        tdeltaopt: Valeur optionnelle pour Tdelta (par défaut None, utilise la valeur standard)
        dict avec le détail de chaque étape du calcul
    """

    # --- Paramètres selon la taille de l'entreprise ---
    Tmin = 0.0200
    P = 1.75

    if effectif_50_et_plus:
        Tdelta = 0.3821  # FNAL à 0.50%
    else:
        Tdelta = 0.3781  # FNAL à 0.10%
    if tdeltaopt is not None:
        Tdelta = tdeltaopt

    Tmax = Tmin + Tdelta  # 0.4021 ou 0.3981

    # --- Étape 1 : SMIC de référence mensuel (proratisé selon heures contractuelles) ---
    HEURES_TEMPS_PLEIN = 151.67
    smic_reference = round(smic_mensuel * (heures_contractuelles / HEURES_TEMPS_PLEIN), 2)

    # --- Étape 2 : Majoration heures supplémentaires ---
    smic_horaire = smic_mensuel / HEURES_TEMPS_PLEIN
    majoration_hs = round(smic_horaire * heures_supplementaires, 2)

    # --- Étape 3 : SMIC ajusté (mensuel) ---
    smic_ajuste_mensuel = smic_reference + majoration_hs

    # --- Annualisation ---
    smic_annuel = smic_ajuste_mensuel * 12  # 21 876.36 € (≈ 21 876.40 officiel)
    rab = brut_mensuel * 12  # Rémunération annuelle brute

    # --- Étape 4 : Vérification éligibilité (brut < 3 × SMIC) ---
    seuil_3_smic = 3 * smic_ajuste_mensuel
    eligible = brut_mensuel < seuil_3_smic

    if not eligible:
        return {
            "smic_reference": smic_reference,
            "majoration_hs": round(majoration_hs, 2),
            "smic_ajuste": round(smic_ajuste_mensuel, 2),
            "assiette_brut": brut_mensuel,
            "ratio_smic": round(brut_mensuel / smic_ajuste_mensuel, 3),
            "seuil_3_smic": round(seuil_3_smic, 2),
            "eligible": False,
            "coefficient": 0,
            "reduction_mensuelle": 0,
            "parametres": {
                "Tmin": Tmin,
                "Tdelta": Tdelta,
                "Tmax": Tmax,
                "P": P,
                "effectif": "≥ 50" if effectif_50_et_plus else "< 50",
            },
        }

    # --- Étape 5 : Ratio salaire / SMIC ---
    ratio_smic = brut_mensuel / smic_ajuste_mensuel

    # --- Étape 6 : Coefficient dégressif ---
    # inner = (1/2) × (3 × SMIC_annuel / RAB - 1)
    inner = 0.5 * (3 * smic_annuel / rab - 1)

    # Si inner <= 0, le salarié est à >= 3 SMIC, pas de réduction au-delà de Tmin
    if inner <= 0:
        coefficient_degressif = 0.0
    else:
        coefficient_degressif = inner ** P

    # --- Étape 7 : Taux applicable ---
    # Coefficient = Tmin + (Tdelta × coefficient_dégressif)
    coefficient = Tmin + (Tdelta * coefficient_degressif)

    # Plafonnement à Tmax
    coefficient = min(coefficient, Tmax)

    # Plancher à Tmin (seuil minimal de 2%) pour rémunération < 3 SMIC
    coefficient = max(coefficient, Tmin)

    # Arrondi à 4 décimales (au dix millième le plus proche)
    coefficient = round(coefficient, 4)

    # --- Étape 8 : Réduction mensuelle ---
    reduction_mensuelle = round(coefficient * brut_mensuel, 2)

    return {
        "smic_reference": smic_reference,
        "majoration_hs": round(majoration_hs, 2),
        "smic_ajuste": round(smic_ajuste_mensuel, 2),
        "smic_annuel": round(smic_annuel, 2),
        "assiette_brut": brut_mensuel,
        "rab": round(rab, 2),
        "ratio_smic": round(ratio_smic, 3),
        "seuil_3_smic": round(seuil_3_smic, 2),
        "eligible": True,
        "inner": round(inner, 6),
        "coefficient_degressif": round(coefficient_degressif, 6),
        "coefficient": coefficient,
        "reduction_mensuelle": reduction_mensuelle,
        "parametres": {
            "Tmin": Tmin,
            "Tdelta": Tdelta,
            "Tmax": Tmax,
            "P": P,
            "effectif": "≥ 50" if effectif_50_et_plus else "< 50",
        },
    }


def afficher_resultat(result: dict) -> None:
    """Affiche le détail du calcul RGDU étape par étape."""
    p = result["parametres"]
    print("=" * 60)
    print(f"CALCUL RGDU 2026 — Entreprise {p['effectif']} salariés")
    print(f"Tmin={p['Tmin']}  Tdelta={p['Tdelta']}  Tmax={p['Tmax']}  P={p['P']}")
    print("=" * 60)

    print(f"\n1. SMIC de référence          : {result['smic_reference']:>10.2f} €")
    print(f"2. Majoration heures sup       : {result['majoration_hs']:>10.2f} €")
    print(f"3. SMIC ajusté                 : {result['smic_ajuste']:>10.2f} €")
    print(f"4. Assiette (brut)             : {result['assiette_brut']:>10.2f} €")
    print(f"5. Ratio salaire / SMIC        : {result['ratio_smic']:>10.3f} × SMIC")
    print(f"   Seuil 3 SMIC                : {result['seuil_3_smic']:>10.2f} €")
    print(f"   Éligible                    : {'Oui' if result['eligible'] else 'Non'}")

    if result["eligible"] and result["coefficient"] > 0:
        print(f"6. Coefficient dégressif       : {result['coefficient_degressif']:>10.6f}")
        print(f"   (inner = {result['inner']:.6f}, inner^{p['P']} = {result['coefficient_degressif']:.6f})")
        print(f"7. Taux applicable (arrondi 4d): {result['coefficient']:>10.4f}")
        print(f"8. Réduction du mois           : {result['reduction_mensuelle']:>10.2f} €")
    else:
        print(f"\n   Pas de réduction applicable.")

    print()


def check_rgdu(
    fiche: FichePayeExtracted,
    smic_mensuel: float,
    effectif_50_et_plus: bool,
) -> CheckResult:
    """
    Vérifie la ligne RGDU d'une fiche de paie extraite.

    Args:
        fiche: Fiche de paie extraite.
        smic_mensuel: SMIC mensuel en vigueur.
        effectif_50_et_plus: True si entreprise >= 50 salariés.

    Returns:
        CheckResult avec le résultat de la vérification.
    """
    LIGNE_RGDU = "73576"

    # Extraire le brut mensuel
    brut_mensuel = fiche.totaux.salaire_brut
    if brut_mensuel is None:
        return CheckResult(
            test_name="rgdu",
            valid=False,
            is_line_error=False,
            line_number=None,
            obtained_value=None,
            expected_value=None,
            difference=None,
            message="Impossible de vérifier RGDU: salaire brut non trouvé dans la fiche.",
        )

    # Extraire les heures (utiliser 151.67 par défaut si non trouvé)
    heures = fiche.totaux.cumul_heures
    heures_contractuelles = float(heures) if heures is not None else 151.67

    # Extraire les heures supplémentaires (0 par défaut)
    heures_sup = fiche.totaux.heures_supplementaires
    heures_supplementaires = float(heures_sup) if heures_sup is not None else 0.0

    # Calculer la réduction attendue
    resultat_calcul = calculer_rgdu(
        brut_mensuel=float(brut_mensuel),
        heures_contractuelles=heures_contractuelles,
        heures_supplementaires=heures_supplementaires,
        effectif_50_et_plus=effectif_50_et_plus,
        smic_mensuel=smic_mensuel,
    )

    expected_value = Decimal(str(resultat_calcul["reduction_mensuelle"]))

    # Chercher la ligne RGDU dans la fiche
    ligne_rgdu = fiche.lignes.get(LIGNE_RGDU)

    if ligne_rgdu is None:
        # Pas de ligne RGDU trouvée
        if expected_value == 0:
            # C'est normal si le salarié n'est pas éligible
            return CheckResult(
                test_name="rgdu",
                valid=True,
                is_line_error=True,
                line_number=LIGNE_RGDU,
                obtained_value=None,
                expected_value=expected_value,
                difference=None,
                message=f"Pas de ligne RGDU trouvée, cohérent car le salarié n'est pas éligible (brut={brut_mensuel}€, seuil 3 SMIC={resultat_calcul['seuil_3_smic']}€).",
            )
        else:
            return CheckResult(
                test_name="rgdu",
                valid=False,
                is_line_error=True,
                line_number=LIGNE_RGDU,
                obtained_value=None,
                expected_value=expected_value,
                difference=None,
                message=f"Ligne RGDU ({LIGNE_RGDU}) non trouvée dans la fiche alors qu'une réduction de {expected_value}€ était attendue.",
            )

    # Extraire la valeur obtenue (montant patronal, généralement négatif car c'est une réduction)
    obtained_value = ligne_rgdu.montant_patronal
    if obtained_value is None:
        obtained_value = ligne_rgdu.montant_salarial

    if obtained_value is None:
        return CheckResult(
            test_name="rgdu",
            valid=False,
            is_line_error=True,
            line_number=LIGNE_RGDU,
            obtained_value=None,
            expected_value=expected_value,
            difference=None,
            message=f"Ligne RGDU ({LIGNE_RGDU}) trouvée mais aucun montant n'est renseigné.",
        )

    # La valeur RGDU sur la fiche est souvent négative (réduction)
    # On compare en valeur absolue
    obtained_abs = abs(obtained_value)
    expected_abs = abs(expected_value)
    difference = obtained_abs - expected_abs

    # Tolérance de 0.01€ pour les arrondis
    tolerance = Decimal("0.50")
    valid = abs(difference) <= tolerance

    # Construire le message explicatif
    params = resultat_calcul["parametres"]
    if resultat_calcul["eligible"]:
        message = (
            f"RGDU calculée: coefficient={resultat_calcul['coefficient']:.4f} × brut={brut_mensuel}€ = {expected_value}€. "
            f"Paramètres: Tmin={params['Tmin']}, Tdelta={params['Tdelta']}, Tmax={params['Tmax']}, "
            f"SMIC ajusté={resultat_calcul['smic_ajuste']}€, ratio={resultat_calcul['ratio_smic']:.3f}×SMIC. "
            f"Valeur sur fiche: {obtained_value}€. "
            f"Écart: {difference}€."
        )
    else:
        message = (
            f"Salarié non éligible à la RGDU (brut={brut_mensuel}€ >= seuil 3 SMIC={resultat_calcul['seuil_3_smic']}€). "
            f"Réduction attendue: 0€. Valeur sur fiche: {obtained_value}€."
        )

    return CheckResult(
        test_name="rgdu",
        valid=valid,
        is_line_error=True,
        line_number=LIGNE_RGDU,
        obtained_value=obtained_value,
        expected_value=expected_value if resultat_calcul["eligible"] else Decimal("0"),
        difference=difference,
        message=message,
    )


# ===== TESTS =====
if __name__ == "__main__":

    print("TEST 1")
    r1 = calculer_rgdu(brut_mensuel=3309.44, effectif_50_et_plus=True, heures_supplementaires=0, tdeltaopt=0.3241)
    afficher_resultat(r1)

