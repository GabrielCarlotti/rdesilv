"""Modèles pour le check des fautes de frappe via LLM."""

from pydantic import BaseModel, Field


class FrappeError(BaseModel):
    """Une erreur de frappe détectée."""

    is_line_error: bool = Field(..., description="True si l'erreur est sur une ligne de cotisation, False si c'est sur employé/employeur")
    line_number: str | None = Field(default=None, description="Numéro de ligne si is_line_error=True")
    field_name: str = Field(..., description="Nom du champ contenant l'erreur (ex: 'libelle', 'nom', 'adresse')")
    error_value: str = Field(..., description="La valeur erronée trouvée")
    expected_value: str = Field(..., description="La valeur correcte attendue")
    explanation: str = Field(..., description="Explication courte de l'erreur")


class FrappeCheckOutput(BaseModel):
    """Sortie du LLM pour le check des fautes de frappe."""

    errors: list[FrappeError] = Field(default_factory=list, description="Liste des erreurs de frappe détectées")
    has_errors: bool = Field(..., description="True si au moins une erreur a été trouvée")


class FrappeCheckInput(BaseModel):
    """Input pour le check des fautes de frappe - données de la fiche de paie."""

    # Infos employeur
    employeur_entreprise: str | None = None
    employeur_etablissement: str | None = None
    employeur_siret: str | None = None
    employeur_ape: str | None = None
    employeur_urssaf: str | None = None
    employeur_convention_collective: str | None = None

    # Infos employé
    employe_nom: str | None = None
    employe_prenom: str | None = None
    employe_adresse: str | None = None
    employe_matricule: str | None = None
    employe_numero_securite_sociale: str | None = None
    employe_qualification: str | None = None
    employe_emploi: str | None = None
    employe_echelon: str | None = None

    # Lignes de cotisations (numéro -> libellé)
    lignes: dict[str, str] = Field(default_factory=dict, description="Dict numéro ligne -> libellé")
