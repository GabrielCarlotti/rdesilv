"""
Check LLM pour détecter les incohérences avec la convention collective.
"""

from pathlib import Path

from src.models.payslip import FichePayeExtracted
from src.models.check import CheckResult
from src.models.convention_check import ConventionCheckOutput, ConventionWarning


# Chemin vers le fichier convention.md
CONVENTION_FILE = Path(__file__).parent.parent / "convention" / "convention.md"


SYSTEM_PROMPT = """Tu es un expert en droit du travail français et en analyse de bulletins de salaire.

Tu dois analyser une fiche de paie et vérifier sa cohérence avec la Convention Collective Nationale de travail des établissements et services pour personnes inadaptées et handicapées du 15 mars 1966 (CCN 66).

IMPORTANT - RÈGLES D'ANALYSE:
1. NE CHERCHE PAS L'ERREUR À TOUT PRIX. Si tout semble cohérent, retourne une liste vide de warnings.
2. Ne signale que les incohérences RÉELLES et SIGNIFICATIVES.
3. Ignore les variations mineures ou les cas où l'information manque pour conclure.
4. Sois PRUDENT: préfère ne rien signaler plutôt que de créer de fausses alertes.

POINTS À VÉRIFIER (si les données sont disponibles):
- Cohérence des classifications et échelons
- Respect des majorations d'ancienneté (Article 39)
- Conformité des indemnités et primes conventionnelles
- Respect des taux de cotisations conventionnels
- Cohérence des mentions employeur/établissement

POINTS À NE PAS VÉRIFIER:
- Les calculs arithmétiques (autres checks s'en occupent)
- Les fautes de frappe (autre check s'en occupe)
- Les éléments hors champ de la convention

Pour chaque incohérence détectée, indique:
- La catégorie (remuneration, anciennete, conges, cotisations, autre)
- Un titre court
- Une description claire
- L'article de la convention concerné si applicable
- La sévérité: 'info' (à vérifier), 'attention' (probable), 'important' (certain)

IMPORTANT: Respecte strictement le schéma JSON demandé."""


def _load_convention() -> str:
    """Charge le contenu du fichier convention.md."""
    if CONVENTION_FILE.exists():
        return CONVENTION_FILE.read_text(encoding="utf-8")
    return "Convention collective non disponible."


def _warning_to_check_result(warning: ConventionWarning) -> CheckResult:
    """Convertit un ConventionWarning en CheckResult."""
    article_ref = f" (Réf: {warning.article_convention})" if warning.article_convention else ""

    return CheckResult(
        test_name="avertissement_llm",
        valid=False,  # Les avertissements sont des "échecs" à investiguer
        is_line_error=False,
        line_number=None,
        obtained_value=None,
        expected_value=None,
        difference=None,
        message=f"[{warning.severite.upper()}] {warning.titre}{article_ref}: {warning.description}",
    )


async def check_convention(fiche: FichePayeExtracted) -> list[CheckResult]:
    """
    Analyse la cohérence de la fiche de paie avec la convention collective via LLM.

    Args:
        fiche: Fiche de paie extraite.

    Returns:
        Liste de CheckResult pour chaque avertissement détecté.
    """
    # Import lazy pour éviter de charger les settings au démarrage
    from src.config import gemini_settings

    results: list[CheckResult] = []

    # Charger la convention
    convention_content = _load_convention()

    # Sérialiser la fiche de paie en JSON
    payslip_json = fiche.model_dump_json(indent=2)

    # Construire le prompt complet
    full_prompt = f"""{SYSTEM_PROMPT}

=== CONVENTION COLLECTIVE (CCN 66) ===
{convention_content}

=== FICHE DE PAIE À ANALYSER (JSON) ===
{payslip_json}

Analyse cette fiche de paie et retourne les éventuelles incohérences avec la convention collective.
Si tout semble cohérent, retourne une liste vide de warnings."""

    try:
        response = await gemini_settings.CLIENT.aio.models.generate_content(
            model=gemini_settings.GEMINI_MODEL_2_5_FLASH,
            contents=full_prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": ConventionCheckOutput,
            },
        )

        # Parser la réponse
        output: ConventionCheckOutput
        if hasattr(response, "parsed") and response.parsed:
            parsed_data = response.parsed
            if isinstance(parsed_data, ConventionCheckOutput):
                output = parsed_data
            elif isinstance(parsed_data, dict):
                output = ConventionCheckOutput.model_validate(parsed_data)
            else:
                output = ConventionCheckOutput.model_validate_json(str(parsed_data))
        else:
            payload = getattr(response, "text", None)
            if isinstance(payload, str):
                output = ConventionCheckOutput.model_validate_json(payload)
            else:
                output = ConventionCheckOutput.model_validate(payload)

        # Convertir les warnings en CheckResult
        for warning in output.warnings:
            results.append(_warning_to_check_result(warning))

        # Si aucun warning, ajouter un résultat positif
        if not output.warnings:
            results.append(CheckResult(
                test_name="avertissement_llm",
                valid=True,
                is_line_error=False,
                line_number=None,
                obtained_value=None,
                expected_value=None,
                difference=None,
                message=f"Aucune incohérence détectée avec la convention collective. {output.resume}",
            ))

    except Exception as err:
        results.append(CheckResult(
            test_name="avertissement_llm",
            valid=False,
            is_line_error=False,
            line_number=None,
            obtained_value=None,
            expected_value=None,
            difference=None,
            message=f"Erreur lors de l'analyse LLM convention: {err}",
        ))

    return results
