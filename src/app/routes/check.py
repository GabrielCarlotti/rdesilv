"""Route de vérification des fiches de paie."""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from src.models.check import CheckReport
from src.app.service.scan import scan_payslip
from src.checking import run_checks

router = APIRouter()


@router.post("/check", response_model=CheckReport)
async def check(
    file: UploadFile = File(...),
    smic_mensuel: float = Form(...),
    effectif_50_et_plus: bool = Form(...),
    plafond_ss: float = Form(...),
    include_frappe_check: bool = Form(default=False),
) -> CheckReport:
    """
    Vérifie une fiche de paie PDF et retourne un rapport de contrôle.

    Args:
        file: Fichier PDF à analyser.
        smic_mensuel: SMIC mensuel brut en vigueur (ex: 1823.03).
        effectif_50_et_plus: True si l'entreprise a 50 salariés ou plus.
        plafond_ss: Plafond de la Sécurité Sociale en vigueur (4005).
        include_frappe_check: Si True, inclut le check des fautes de frappe via LLM.

    Returns:
        CheckReport: Rapport avec les résultats de tous les tests de vérification.
    """
    try:
        # Extraire les données de la fiche
        fiche = await scan_payslip(file)

        # Exécuter les vérifications
        return await run_checks(
            fiche,
            smic_mensuel,
            effectif_50_et_plus,
            plafond_ss,
            include_frappe_check,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la vérification: {e}")
