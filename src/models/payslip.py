"""
Modèles Pydantic pour l'extraction des fiches de paie.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class EmployerInfo(BaseModel):
    """Informations sur l'employeur."""

    entreprise: str | None = Field(default=None, description="Nom de l'entreprise")
    etablissement: str | None = Field(default=None, description="Nom de l'établissement")
    adresse: str | None = Field(default=None, description="Adresse de l'établissement")
    code_postal: str | None = Field(default=None, description="Code postal")
    ville: str | None = Field(default=None, description="Ville")
    siret: str | None = Field(default=None, description="Numéro SIRET")
    ape: str | None = Field(default=None, description="Code APE/NAF")
    urssaf: str | None = Field(default=None, description="URSSAF de rattachement")
    numero_cotisant: str | None = Field(default=None, description="Numéro de cotisant")
    convention_collective: str | None = Field(default=None, description="Convention collective applicable")


class EmployeeInfo(BaseModel):
    """Informations sur l'employé."""

    nom: str | None = Field(default=None, description="Nom de famille")
    prenom: str | None = Field(default=None, description="Prénom")
    nom_complet: str | None = Field(default=None, description="Nom complet")
    adresse: str | None = Field(default=None, description="Adresse de l'employé")
    code_postal: str | None = Field(default=None, description="Code postal")
    ville: str | None = Field(default=None, description="Ville")
    matricule: str | None = Field(default=None, description="Matricule employé")
    numero_securite_sociale: str | None = Field(default=None, description="Numéro de sécurité sociale")
    date_entree: date | None = Field(default=None, description="Date d'entrée dans l'entreprise")
    qualification: str | None = Field(default=None, description="Qualification conventionnelle")
    emploi: str | None = Field(default=None, description="Intitulé du poste")
    echelon: str | None = Field(default=None, description="Échelon")
    coefficient: Decimal | None = Field(default=None, description="Coefficient")
    categorie: str | None = Field(default=None, description="Catégorie (Cadre, Non-cadre, etc.)")


class PayPeriod(BaseModel):
    """Période de paie."""

    date_debut: date | None = Field(default=None, description="Date de début de période")
    date_fin: date | None = Field(default=None, description="Date de fin de période")
    mois: int | None = Field(default=None, ge=1, le=12, description="Mois de la paie")
    annee: int | None = Field(default=None, description="Année de la paie")
    numero_bulletin: str | None = Field(default=None, description="Numéro du bulletin de salaire")


class PayslipLine(BaseModel):
    """Ligne de cotisation/rubrique du bulletin de paie."""

    numero: str | None = Field(default=None, description="Numéro de la ligne/rubrique")
    libelle: str = Field(..., description="Libellé de la ligne")
    base: Decimal | None = Field(default=None, description="Base de calcul")
    taux_salarial: Decimal | None = Field(default=None, description="Taux salarial (%)")
    montant_salarial: Decimal | None = Field(default=None, description="Montant retenue salariale")
    taux_patronal: Decimal | None = Field(default=None, description="Taux patronal (%)")
    montant_patronal: Decimal | None = Field(default=None, description="Montant cotisation patronale")


class LeaveBalance(BaseModel):
    """Solde des congés."""

    conges_n: Decimal | None = Field(default=None, description="Congés année N")
    conges_n1: Decimal | None = Field(default=None, description="Congés année N-1")
    conges_n2: Decimal | None = Field(default=None, description="Congés année N-2")
    rtt: Decimal | None = Field(default=None, description="RTT acquis")
    rtt_pris: Decimal | None = Field(default=None, description="RTT pris")
    anciennete: Decimal | None = Field(default=None, description="Congés ancienneté")


class PayslipTotals(BaseModel):
    """Totaux et cumuls du bulletin de paie."""

    # Montants du mois
    salaire_brut: Decimal | None = Field(default=None, description="Salaire brut mensuel")
    total_retenues_salariales: Decimal | None = Field(default=None, description="Total des retenues salariales")
    total_cotisations_patronales: Decimal | None = Field(default=None, description="Total des cotisations patronales")
    net_avant_impot: Decimal | None = Field(default=None, description="Net à payer avant impôt (PAS)")
    net_imposable: Decimal | None = Field(default=None, description="Net imposable mensuel")
    net_social: Decimal | None = Field(default=None, description="Net social")
    net_a_payer: Decimal | None = Field(default=None, description="Net à payer après impôt")

    # Prélèvement à la source
    taux_pas: Decimal | None = Field(default=None, description="Taux du prélèvement à la source (%)")
    montant_pas: Decimal | None = Field(default=None, description="Montant du prélèvement à la source")
    type_taux_pas: str | None = Field(default=None, description="Type de taux PAS (personnalisé, neutre, etc.)")

    # Heures
    heures_travaillees: Decimal | None = Field(default=None, description="Heures travaillées dans le mois")
    heures_supplementaires: Decimal | None = Field(default=None, description="Heures supplémentaires")

    # Cumuls annuels
    cumul_brut: Decimal | None = Field(default=None, description="Cumul brut depuis janvier")
    cumul_net_imposable: Decimal | None = Field(default=None, description="Cumul net imposable depuis janvier")
    cumul_heures: Decimal | None = Field(default=None, description="Cumul heures depuis janvier")
    cumul_avantages_nature: Decimal | None = Field(default=None, description="Cumul avantages en nature")

    # Mode de paiement
    mode_paiement: str | None = Field(default=None, description="Mode de paiement (virement, chèque, etc.)")
    date_paiement: date | None = Field(default=None, description="Date de paiement")
    iban: str | None = Field(default=None, description="IBAN du compte de versement")


class FichePayeExtracted(BaseModel):
    """
    Modèle complet d'une fiche de paie extraite.

    Contient toutes les informations structurées extraites d'un bulletin de salaire PDF.
    """

    # Métadonnées d'extraction
    source_file: str | None = Field(default=None, description="Chemin du fichier PDF source")
    extraction_success: bool = Field(default=True, description="Indique si l'extraction a réussi")
    extraction_errors: list[str] = Field(default_factory=list, description="Erreurs rencontrées lors de l'extraction")

    # Informations principales
    employeur: EmployerInfo = Field(default_factory=EmployerInfo, description="Informations employeur")
    employe: EmployeeInfo = Field(default_factory=EmployeeInfo, description="Informations employé")
    periode: PayPeriod = Field(default_factory=PayPeriod, description="Période de paie")

    # Lignes de cotisations (dict par numéro de ligne)
    lignes: dict[str, PayslipLine] = Field(
        default_factory=dict,
        description="Dictionnaire des lignes de cotisations indexé par numéro de ligne"
    )

    # Liste ordonnée des lignes (pour conserver l'ordre d'apparition)
    lignes_liste: list[PayslipLine] = Field(
        default_factory=list,
        description="Liste ordonnée des lignes de cotisations"
    )

    # Totaux et cumuls
    totaux: PayslipTotals = Field(default_factory=PayslipTotals, description="Totaux et cumuls")

    # Soldes congés
    conges: LeaveBalance = Field(default_factory=LeaveBalance, description="Solde des congés")

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v) if v is not None else None,
            date: lambda v: v.isoformat() if v is not None else None,
        }
