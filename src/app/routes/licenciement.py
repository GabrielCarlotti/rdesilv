"""Route de calcul d'indemnité de licenciement et rupture conventionnelle."""

from fastapi import APIRouter, HTTPException

from src.models.licenciement import (
    LicenciementInput,
    LicenciementResult,
    TypeRupture,
    ConventionCollective,
)
from src.services.licenciement import calculer_indemnite_licenciement

router = APIRouter()


@router.post("/licenciement", response_model=LicenciementResult)
async def calculer_licenciement(data: LicenciementInput) -> LicenciementResult:
    """
    Calcule l'indemnité de licenciement ou rupture conventionnelle.

    ## Licenciement
    - Motif requis (personnel, économique, inaptitude, faute)
    - Faute grave/lourde = pas d'indemnité
    - Le préavis s'ajoute à l'ancienneté (même si dispensé)
    - Indemnité doublée pour inaptitude professionnelle

    ## Rupture conventionnelle
    - Pas de motif requis
    - Pas de préavis (ancienneté = date fin convenue)
    - Même calcul minimum que le licenciement
    - Possibilité de négocier un supralégal

    ## Calcul commun
    - Ancienneté minimum: 8 mois
    - Salaire de référence: meilleur entre 12 et 3 derniers mois
    - Principe de faveur entre indemnité légale et conventionnelle
    - Formule légale: 1/4 mois par année (≤10 ans) + 1/3 mois par année (>10 ans)

    ## CCN 1966 (si applicable)
    - Ancienneté minimum: 2 ans
    - Calcul: 1/2 mois par année
    - Plafond: 6 mois de salaire
    - Plafond: rémunérations jusqu'à 65 ans
    """
    try:
        # Validation: motif requis pour licenciement
        if data.type_rupture == TypeRupture.LICENCIEMENT and data.motif is None:
            raise HTTPException(
                status_code=400,
                detail="Le motif est requis pour un licenciement."
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
