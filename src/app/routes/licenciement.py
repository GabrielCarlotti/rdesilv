"""Route de calcul d'indemnité de licenciement et rupture conventionnelle."""

from io import BytesIO

from fastapi import APIRouter, HTTPException, UploadFile, File
import fitz  # PyMuPDF

from src.models.licenciement import (
    LicenciementInput,
    LicenciementResult,
    LicenciementPdfExtraction,
    SalaireMensuel,
    TypeRupture,
    ConventionCollective,
)
from src.services.licenciement import calculer_indemnite_licenciement
from src.app.service.scan import scan_payslip

router = APIRouter()


def _detect_convention_collective(convention_brute: str | None) -> ConventionCollective:
    """Détecte la convention collective depuis le texte brut."""
    if not convention_brute:
        return ConventionCollective.AUCUNE

    convention_lower = convention_brute.lower()

    # Détection CCN 1966
    if "1966" in convention_lower or "15 mars" in convention_lower or "inadaptées" in convention_lower or "handicapées" in convention_lower:
        return ConventionCollective.CCN_1966

    return ConventionCollective.AUCUNE


@router.post("/licenciement", response_model=LicenciementResult)
async def calculer_licenciement(data: LicenciementInput) -> LicenciementResult:
    """
    Calcule l'indemnité de licenciement ou rupture conventionnelle.

    ## Dates requises
    - `date_entree`: Date d'entrée dans l'entreprise
    - `date_notification`: Date de notification du licenciement (requis pour licenciement)
    - `date_fin_contrat`: Date de fin du contrat (fin préavis pour licenciement, date convenue pour rupture conv.)

    ## Licenciement
    - Motif requis (personnel, économique, inaptitude, faute)
    - Faute grave/lourde = pas d'indemnité
    - Préavis calculé automatiquement (date_fin_contrat - date_notification)
    - Indemnité doublée pour inaptitude professionnelle

    ## Rupture conventionnelle
    - Pas de motif requis
    - Pas de préavis
    - Possibilité de négocier un supralégal

    ## CCN 1966 (si applicable)
    - Ancienneté minimum: 2 ans
    - Calcul: 1/2 mois par année
    - Plafond: 6 mois de salaire
    """
    try:
        # Validation: motif requis pour licenciement
        if data.type_rupture == TypeRupture.LICENCIEMENT:
            if data.motif is None:
                raise HTTPException(
                    status_code=400,
                    detail="Le motif est requis pour un licenciement."
                )
            if data.date_notification is None:
                raise HTTPException(
                    status_code=400,
                    detail="La date de notification est requise pour un licenciement."
                )

        # Validation: cohérence des dates
        if data.date_fin_contrat < data.date_entree:
            raise HTTPException(
                status_code=400,
                detail="La date de fin de contrat ne peut pas être antérieure à la date d'entrée."
            )

        if data.type_rupture == TypeRupture.LICENCIEMENT and data.date_notification:
            if data.date_notification < data.date_entree:
                raise HTTPException(
                    status_code=400,
                    detail="La date de notification ne peut pas être antérieure à la date d'entrée."
                )
            if data.date_fin_contrat < data.date_notification:
                raise HTTPException(
                    status_code=400,
                    detail="La date de fin de contrat ne peut pas être antérieure à la date de notification."
                )

        # Validation spécifique CCN 1966
        if data.convention_collective == ConventionCollective.CCN_1966:
            if data.age_salarie is None:
                raise HTTPException(
                    status_code=400,
                    detail="L'âge du salarié est requis pour la CCN 1966 (plafond 65 ans)."
                )
            if data.salaire_mensuel_actuel is None:
                raise HTTPException(
                    status_code=400,
                    detail="Le salaire mensuel actuel est requis pour la CCN 1966 (plafond 65 ans)."
                )

        return calculer_indemnite_licenciement(data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du calcul de l'indemnité: {e}"
        )


@router.post("/licenciementpdf", response_model=LicenciementPdfExtraction)
async def extraire_donnees_licenciement(
    file: UploadFile = File(..., description="PDF contenant les 12 fiches de paie (une par page ou groupe de pages)")
) -> LicenciementPdfExtraction:
    """
    Extrait les données des 12 dernières fiches de paie pour pré-remplir le formulaire de licenciement.

    ## Entrée
    - PDF contenant les 12 fiches de paie concaténées (du plus récent au plus ancien)

    ## Données extraites
    - Date d'entrée dans l'entreprise
    - Convention collective
    - Salaires bruts des 12 derniers mois

    ## Utilisation
    Le frontend utilise ces données pour pré-remplir le formulaire,
    puis appelle `/licenciement` avec les données complétées par l'utilisateur.
    """
    errors: list[str] = []
    salaires_extraits: list[SalaireMensuel] = []
    date_entree = None
    convention_brute = None
    convention_collective = ConventionCollective.AUCUNE

    try:
        # Lire le PDF
        pdf_content = await file.read()
        pdf_document = fitz.open(stream=pdf_content, filetype="pdf")

        # Extraire chaque page comme une fiche potentielle
        # Note: On suppose une fiche par page, mais on pourrait améliorer la détection
        for page_num in range(len(pdf_document)):
            try:
                # Créer un PDF d'une seule page
                single_page_pdf = fitz.open()
                single_page_pdf.insert_pdf(pdf_document, from_page=page_num, to_page=page_num)

                # Convertir en bytes
                pdf_bytes = single_page_pdf.tobytes()
                single_page_pdf.close()

                # Créer un UploadFile fictif pour scan_payslip
                from starlette.datastructures import UploadFile as StarletteUploadFile

                fake_file = StarletteUploadFile(
                    file=BytesIO(pdf_bytes),
                    filename=f"page_{page_num + 1}.pdf",
                )

                # Extraire la fiche
                fiche = await scan_payslip(fake_file)  # type: ignore

                # Récupérer la date d'entrée (on prend la première trouvée)
                if date_entree is None and fiche.employe.date_entree:
                    date_entree = fiche.employe.date_entree

                # Récupérer la convention collective (on prend la première trouvée)
                if convention_brute is None and fiche.employeur.convention_collective:
                    convention_brute = fiche.employeur.convention_collective
                    convention_collective = _detect_convention_collective(convention_brute)

                # Récupérer le salaire brut si disponible
                if fiche.totaux.salaire_brut and fiche.periode.mois and fiche.periode.annee:
                    salaires_extraits.append(SalaireMensuel(
                        mois=fiche.periode.mois,
                        annee=fiche.periode.annee,
                        salaire_brut=fiche.totaux.salaire_brut,
                    ))

            except Exception as e:
                errors.append(f"Erreur page {page_num + 1}: {str(e)}")

        pdf_document.close()

        # Trier les salaires par date (du plus récent au plus ancien)
        salaires_extraits.sort(key=lambda s: (s.annee, s.mois), reverse=True)

        # Limiter à 12 mois
        salaires_extraits = salaires_extraits[:12]

        # Extraire juste les montants pour le front
        salaires_12_derniers_mois = [s.salaire_brut for s in salaires_extraits]

        return LicenciementPdfExtraction(
            extraction_success=len(salaires_extraits) > 0,
            extraction_errors=errors,
            date_entree=date_entree,
            convention_collective=convention_collective,
            convention_collective_brute=convention_brute,
            salaires_extraits=salaires_extraits,
            salaires_12_derniers_mois=salaires_12_derniers_mois,
            nombre_fiches_extraites=len(salaires_extraits),
        )

    except Exception as e:
        return LicenciementPdfExtraction(
            extraction_success=False,
            extraction_errors=[f"Erreur lors de l'extraction: {str(e)}"],
        )
