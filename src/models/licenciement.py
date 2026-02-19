"""Modèles pour le calcul d'indemnité de licenciement et rupture conventionnelle."""

from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field


class TypeRupture(str, Enum):
    """Type de rupture du contrat."""
    LICENCIEMENT = "licenciement"
    RUPTURE_CONVENTIONNELLE = "rupture_conventionnelle"


class MotifLicenciement(str, Enum):
    """Motif du licenciement (uniquement pour type=licenciement)."""
    PERSONNEL = "personnel"
    ECONOMIQUE = "economique"
    INAPTITUDE_PROFESSIONNELLE = "inaptitude_professionnelle"
    INAPTITUDE_NON_PROFESSIONNELLE = "inaptitude_non_professionnelle"
    FAUTE_GRAVE = "faute_grave"
    FAUTE_LOURDE = "faute_lourde"


class ConventionCollective(str, Enum):
    """Convention collective applicable."""
    AUCUNE = "aucune"
    CCN_1966 = "ccn_1966"  # Convention collective nationale du 15 mars 1966


class PeriodeTravail(BaseModel):
    """Période de travail avec coefficient temps (1.0 = temps plein)."""
    duree_mois: int = Field(..., description="Durée de la période en mois")
    coefficient_temps: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Coefficient temps de travail (1.0 = temps plein, 0.5 = mi-temps)"
    )


class LicenciementInput(BaseModel):
    """Données d'entrée pour le calcul de l'indemnité de licenciement ou rupture conventionnelle."""

    # Type de rupture
    type_rupture: TypeRupture = Field(
        default=TypeRupture.LICENCIEMENT,
        description="Type de rupture: licenciement ou rupture_conventionnelle"
    )

    # Ancienneté brute (sans préavis)
    anciennete_mois_brute: int = Field(
        ...,
        ge=0,
        description="Ancienneté en mois du premier jour du contrat jusqu'à la date de notification (licenciement) ou date de fin convenue (rupture conv.)"
    )

    # Préavis (uniquement pour licenciement)
    preavis_mois: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Durée du préavis en mois (0 à 3). S'ajoute à l'ancienneté pour le calcul, même si dispensé. Ignoré pour rupture conventionnelle."
    )

    # Motif (uniquement pour licenciement)
    motif: MotifLicenciement | None = Field(
        default=None,
        description="Motif du licenciement (requis pour licenciement, ignoré pour rupture conventionnelle)"
    )

    # Indemnité supralégale négociée (uniquement pour rupture conventionnelle)
    indemnite_supralegale: Decimal | None = Field(
        default=None,
        ge=0,
        description="Montant supralégal négocié en plus du minimum légal/conventionnel (rupture conventionnelle uniquement)"
    )

    # Convention collective
    convention_collective: ConventionCollective = Field(
        default=ConventionCollective.AUCUNE,
        description="Convention collective applicable"
    )

    # Salaires pour le calcul du salaire de référence
    salaires_12_derniers_mois: list[Decimal] = Field(
        ...,
        min_length=1,
        max_length=12,
        description="Salaires bruts des 12 derniers mois (ou moins si ancienneté < 12 mois)"
    )

    # Primes annuelles versées dans les 3 derniers mois (pour proratisation)
    primes_annuelles_3_derniers_mois: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Total des primes annuelles/exceptionnelles versées dans les 3 derniers mois"
    )

    # Périodes de travail (temps plein/partiel)
    periodes_travail: list[PeriodeTravail] = Field(
        default_factory=list,
        description="Périodes de travail avec leur coefficient temps. Si vide, on considère temps plein sur toute l'ancienneté."
    )

    # Périodes suspendues à déduire (congé sans solde, sabbatique, maladie non pro, grève)
    mois_suspendus_non_comptes: int = Field(
        default=0,
        ge=0,
        description="Nombre de mois à déduire de l'ancienneté (congé sans solde, sabbatique, maladie non pro, grève)"
    )

    # Congé parental temps plein (compte pour moitié)
    mois_conge_parental_temps_plein: int = Field(
        default=0,
        ge=0,
        description="Nombre de mois de congé parental à temps plein (compte pour 50%)"
    )

    # Pour la CCN 1966 : âge du salarié (pour le plafond jusqu'à 65 ans)
    age_salarie: int | None = Field(
        default=None,
        ge=16,
        le=70,
        description="Âge du salarié (requis pour CCN 1966 pour calculer le plafond)"
    )

    # Salaire mensuel actuel (pour le plafond CCN 1966)
    salaire_mensuel_actuel: Decimal | None = Field(
        default=None,
        description="Salaire mensuel actuel (requis pour CCN 1966 pour calculer le plafond jusqu'à 65 ans)"
    )


class LicenciementResult(BaseModel):
    """Résultat du calcul d'indemnité de licenciement ou rupture conventionnelle."""

    # Type de rupture
    type_rupture: TypeRupture = Field(..., description="Type de rupture effectué")

    # Montant final
    montant_indemnite: Decimal = Field(..., description="Montant total de l'indemnité (minimum légal/conventionnel + supralégal si applicable)")

    # Montant minimum (légal ou conventionnel)
    montant_minimum: Decimal = Field(..., description="Montant minimum légal ou conventionnel (plancher)")

    # Détails du calcul
    salaire_reference: Decimal = Field(..., description="Salaire de référence utilisé")
    methode_salaire_reference: str = Field(..., description="Méthode utilisée pour le salaire de référence")
    anciennete_retenue_mois: int = Field(..., description="Ancienneté retenue en mois")
    anciennete_retenue_annees: Decimal = Field(..., description="Ancienneté retenue en années")

    # Indemnités calculées
    indemnite_legale: Decimal = Field(..., description="Indemnité légale calculée")
    indemnite_conventionnelle: Decimal | None = Field(
        default=None,
        description="Indemnité conventionnelle si applicable"
    )

    # Multiplicateur appliqué
    multiplicateur: Decimal = Field(
        default=Decimal("1"),
        description="Multiplicateur appliqué (2 pour inaptitude pro)"
    )

    # Préavis (licenciement uniquement)
    preavis_mois: int = Field(default=0, description="Mois de préavis inclus dans l'ancienneté")

    # Supralégal (rupture conventionnelle uniquement)
    indemnite_supralegale: Decimal = Field(
        default=Decimal("0"),
        description="Montant supralégal négocié (rupture conventionnelle)"
    )

    # Plafonds
    plafond_applique: bool = Field(default=False, description="Si un plafond a été appliqué")
    plafond_description: str | None = Field(default=None, description="Description du plafond appliqué")

    # Explication
    explication: str = Field(..., description="Phrase résumant le calcul et les options choisies")

    # Éligibilité
    eligible: bool = Field(..., description="Si le salarié est éligible à l'indemnité")
    raison_ineligibilite: str | None = Field(default=None, description="Raison si non éligible")
