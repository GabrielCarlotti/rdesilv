"""Modèles pour les rapports de vérification."""

from decimal import Decimal

from pydantic import BaseModel, Field


class CheckResult(BaseModel):
    """Résultat d'un test de vérification."""

    test_name: str = Field(..., description="Nom du test (ex: rgdu, csg)")
    valid: bool = Field(..., description="True si le test passe")
    is_line_error: bool = Field(..., description="True si erreur sur une ligne, False si erreur de total")
    line_number: str | None = Field(default=None, description="Numéro de ligne si is_line_error=True")
    obtained_value: Decimal | None = Field(default=None, description="Valeur trouvée dans la fiche")
    expected_value: Decimal | None = Field(default=None, description="Valeur calculée attendue")
    difference: Decimal | None = Field(default=None, description="Écart entre obtenu et attendu")
    message: str = Field(..., description="Explication de la formule appliquée ou de l'erreur")


class CheckReport(BaseModel):
    """Rapport complet de vérification d'une fiche de paie."""

    source_file: str | None = Field(default=None, description="Fichier source")
    extraction_success: bool = Field(default=True, description="Si l'extraction a réussi")
    checks: list[CheckResult] = Field(default_factory=list, description="Liste des résultats de tests")
    all_valid: bool = Field(default=True, description="True si tous les tests passent")
    total_checks: int = Field(default=0, description="Nombre total de tests exécutés")
    passed_checks: int = Field(default=0, description="Nombre de tests réussis")
    failed_checks: int = Field(default=0, description="Nombre de tests échoués")
