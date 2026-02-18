"""
Check LLM pour détecter les fautes de frappe dans la fiche de paie.
"""

from typing import cast

from src.models.payslip import FichePayeExtracted
from src.models.check import CheckResult
from src.models.frappe import FrappeCheckInput, FrappeCheckOutput, FrappeError
from src.config import gemini_settings


SYSTEM_PROMPT = """Tu es un expert en analyse de bulletins de salaire français.

Ta mission est de détecter les FAUTES DE FRAPPE uniquement dans les données de la fiche de paie.

Exemples de fautes de frappe à détecter:
- "Cotisation Viellesse" au lieu de "Cotisation Vieillesse"
- "Prevoyance" au lieu de "Prévoyance"
- "Allocatons familiales" au lieu de "Allocations familiales"
- "STRASBOUR" au lieu de "STRASBOURG"
- "Régime locl" au lieu de "Régime local"
- Erreurs d'accents manquants ou incorrects
- Lettres inversées ou manquantes dans les libellés

NE PAS signaler:
- Les abréviations volontaires (ex: "Contrib." pour "Contribution")
- Les codes ou numéros
- Les formats de date ou montants
- Les fautes d'accent
- Les noms propres (sauf fautes évidentes)

Analyse les données et retourne UNIQUEMENT les vraies fautes de frappe.
Si aucune faute n'est trouvée, retourne une liste vide.

TU AS L'INTERDICTION FORMELLE DE SIGNALER DES ERREURS D'ACCENTS, CE N'EST PAS UNE FAUTE DE FRAPPE.

IMPORTANT: Respecte strictement le schéma JSON demandé."""


def _build_input(fiche: FichePayeExtracted) -> FrappeCheckInput:
    """Construit l'input pour le LLM à partir de la fiche."""
    lignes_dict = {}
    for numero, ligne in fiche.lignes.items():
        lignes_dict[numero] = ligne.libelle

    return FrappeCheckInput(
        employeur_entreprise=fiche.employeur.entreprise,
        employeur_etablissement=fiche.employeur.etablissement,
        employeur_siret=fiche.employeur.siret,
        employeur_ape=fiche.employeur.ape,
        employeur_urssaf=fiche.employeur.urssaf,
        employeur_convention_collective=fiche.employeur.convention_collective,
        employe_nom=fiche.employe.nom,
        employe_prenom=fiche.employe.prenom,
        employe_adresse=fiche.employe.adresse,
        employe_matricule=fiche.employe.matricule,
        employe_numero_securite_sociale=fiche.employe.numero_securite_sociale,
        employe_qualification=fiche.employe.qualification,
        employe_emploi=fiche.employe.emploi,
        employe_echelon=fiche.employe.echelon,
        lignes=lignes_dict,
    )


def _frappe_error_to_check_result(error: FrappeError) -> CheckResult:
    """Convertit une FrappeError en CheckResult."""
    return CheckResult(
        test_name="frappe",
        valid=False,
        is_line_error=error.is_line_error,
        line_number=error.line_number,
        obtained_value=None,  # On utilise le message pour les strings
        expected_value=None,
        difference=None,
        message=f"Faute de frappe dans '{error.field_name}': '{error.error_value}' → '{error.expected_value}'. {error.explanation}",
    )


async def check_frappe(fiche: FichePayeExtracted) -> list[CheckResult]:
    """
    Détecte les fautes de frappe dans une fiche de paie via LLM.

    Args:
        fiche: Fiche de paie extraite.

    Returns:
        Liste de CheckResult pour chaque faute de frappe détectée.
    """
    results: list[CheckResult] = []

    # Construire l'input
    check_input = _build_input(fiche)
    input_json = check_input.model_dump_json(indent=2)

    try:
        response = await gemini_settings.CLIENT.aio.models.generate_content(
            model=gemini_settings.GEMINI_MODEL_2_5_FLASH,
            contents=f"{SYSTEM_PROMPT}\n\nDonnées de la fiche de paie à analyser:\n{input_json}",
            config={
                "response_mime_type": "application/json",
                "response_schema": FrappeCheckOutput,
            },
        )

        # Parser la réponse
        output: FrappeCheckOutput
        if hasattr(response, "parsed") and response.parsed:
            parsed_data = response.parsed
            if isinstance(parsed_data, FrappeCheckOutput):
                output = parsed_data
            elif isinstance(parsed_data, dict):
                output = FrappeCheckOutput.model_validate(parsed_data)
            else:
                output = FrappeCheckOutput.model_validate(cast(dict, parsed_data))
        else:
            payload = getattr(response, "text", None)
            if isinstance(payload, str):
                output = FrappeCheckOutput.model_validate_json(payload)
            else:
                output = FrappeCheckOutput.model_validate(payload)

        # Convertir les erreurs en CheckResult
        for error in output.errors:
            results.append(_frappe_error_to_check_result(error))

        # Si aucune erreur, ajouter un résultat positif
        if not output.has_errors:
            results.append(CheckResult(
                test_name="frappe",
                valid=True,
                is_line_error=False,
                line_number=None,
                obtained_value=None,
                expected_value=None,
                difference=None,
                message="Aucune faute de frappe détectée.",
            ))

    except Exception as err:
        results.append(CheckResult(
            test_name="frappe",
            valid=False,
            is_line_error=False,
            line_number=None,
            obtained_value=None,
            expected_value=None,
            difference=None,
            message=f"Erreur lors de l'analyse LLM: {err}",
        ))

    return results
