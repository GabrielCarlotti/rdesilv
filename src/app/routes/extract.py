"""Route de traitement des fiches de paie."""

from fastapi import APIRouter, UploadFile, File, HTTPException

from src.models.payslip import FichePayeExtracted
from src.app.service.scan import scan_payslip

router = APIRouter()


@router.post("/extraction", response_model=FichePayeExtracted)
async def extract(file: UploadFile = File(...)) -> FichePayeExtracted:
    """
    Traite une fiche de paie PDF et extrait les données.

    Args:
        file: Fichier PDF à analyser.

    Returns:
        FichePayeExtracted: Les données structurées extraites.
    """
    try:
        return await scan_payslip(file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement: {e}")
