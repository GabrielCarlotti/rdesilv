"""Service de scan des fiches de paie."""

import tempfile
from pathlib import Path
from fastapi import UploadFile
from src.models.payslip import FichePayeExtracted
from src.ingestion import extract_payslip
from src.checks import calculer_rgdu


async def check_payslip(file: UploadFile):
    """
    Scanne une fiche de paie PDF uploadée et extrait les données avant de run tous les tests de validité et d'afficher leurs résultats.

    Args:
        file: Fichier PDF uploadé via FastAPI.

    Returns:
        FichePayeExtracted: Les données structurées extraites du bulletin.

    Raises:
        ValueError: Si le fichier n'est pas un PDF.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise ValueError("Le fichier doit être un PDF")

    # Sauvegarder temporairement le fichier pour pdfplumber
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        result = extract_payslip(tmp_path)
        # Remplacer le chemin temporaire par le nom original
        result.source_file = file.filename


        return result
    finally:
        # Nettoyer le fichier temporaire
        tmp_path.unlink(missing_ok=True)
