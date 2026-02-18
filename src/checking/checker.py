"""Service de vérification des fiches de paie."""

from src.models.payslip import FichePayeExtracted
from src.models.check import CheckReport, CheckResult
from src.checks import check_rgdu


def run_checks(
    fiche: FichePayeExtracted,
    smic_mensuel: float,
    effectif_50_et_plus: bool,
) -> CheckReport:
    """
    Exécute tous les tests de vérification sur une fiche de paie.

    Args:
        fiche: Fiche de paie extraite.
        smic_mensuel: SMIC mensuel en vigueur.
        effectif_50_et_plus: True si entreprise >= 50 salariés.

    Returns:
        CheckReport avec les résultats de tous les tests.
    """
    results: list[CheckResult] = []

    # Test RGDU
    results.append(check_rgdu(fiche, smic_mensuel, effectif_50_et_plus))

    # Ajouter d'autres tests ici au fur et à mesure
    # results.append(check_csg(fiche, ...))
    # results.append(check_vieillesse(fiche, ...))

    # Compiler les stats
    passed = sum(1 for r in results if r.valid)
    failed = len(results) - passed

    return CheckReport(
        source_file=fiche.source_file,
        extraction_success=fiche.extraction_success,
        checks=results,
        all_valid=failed == 0,
        total_checks=len(results),
        passed_checks=passed,
        failed_checks=failed,
    )
