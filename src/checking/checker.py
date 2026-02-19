"""Service de vérification des fiches de paie."""

from src.models.payslip import FichePayeExtracted
from src.models.check import CheckReport, CheckResult
from src.checks import (
    check_rgdu,
    check_bases,
    check_fiscal,
    check_csg,
    check_allocations_familiales,
    check_frappe,
    check_convention,
)


async def run_checks(
    fiche: FichePayeExtracted,
    smic_mensuel: float,
    effectif_50_et_plus: bool,
    plafond_ss: float,
    include_frappe_check: bool = False,
    include_analyse_llm: bool = False,
) -> CheckReport:
    """
    Exécute tous les tests de vérification sur une fiche de paie.

    Args:
        fiche: Fiche de paie extraite.
        smic_mensuel: SMIC mensuel en vigueur.
        effectif_50_et_plus: True si entreprise >= 50 salariés.
        plafond_ss: Plafond de la Sécurité Sociale en vigueur.
        include_frappe_check: Si True, inclut le check des fautes de frappe via LLM.
        include_analyse_llm: Si True, inclut l'analyse de cohérence convention collective via LLM.

    Returns:
        CheckReport avec les résultats de tous les tests.
    """
    results: list[CheckResult] = []

    # Test RGDU
    results.append(check_rgdu(fiche, smic_mensuel, effectif_50_et_plus))

    # Test des bases de cotisations (T1/T2/TA/TB/APEC)
    results.extend(check_bases(fiche, plafond_ss))

    # Test fiscal (reconstruction du net imposable)
    results.append(check_fiscal(fiche))

    # Test CSG (reconstruction de la base CSG)
    results.append(check_csg(fiche))

    # Test allocations familiales (taux plein vs réduit)
    results.append(check_allocations_familiales(fiche, smic_mensuel))

    # Test fautes de frappe via LLM (optionnel)
    if include_frappe_check:
        frappe_results = await check_frappe(fiche)
        results.extend(frappe_results)

    # Analyse cohérence convention collective via LLM (optionnel)
    if include_analyse_llm:
        convention_results = await check_convention(fiche)
        results.extend(convention_results)

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
