"""Service de calcul de l'indemnité de licenciement et rupture conventionnelle."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from src.models.licenciement import (
    LicenciementInput,
    LicenciementResult,
    TypeRupture,
    MotifLicenciement,
    ConventionCollective,
)


def _calculer_mois_entre_dates(date_debut: date, date_fin: date) -> int:
    """
    Calcule le nombre de mois complets entre deux dates.

    Le calcul est fait en mois entiers (proratisation des jours).
    """
    if date_fin < date_debut:
        return 0

    # Calcul en mois
    mois = (date_fin.year - date_debut.year) * 12 + (date_fin.month - date_debut.month)

    # Ajuster si le jour de fin est avant le jour de début (mois incomplet)
    if date_fin.day < date_debut.day:
        mois -= 1

    return max(0, mois)


def _calculer_preavis_mois(data: LicenciementInput) -> int:
    """
    Calcule la durée du préavis en mois.

    Pour licenciement: préavis = date_fin_contrat - date_notification
    Pour rupture conventionnelle: pas de préavis (0)
    """
    if data.type_rupture == TypeRupture.RUPTURE_CONVENTIONNELLE:
        return 0

    if data.date_notification is None:
        return 0

    return _calculer_mois_entre_dates(data.date_notification, data.date_fin_contrat)


def _calculer_anciennete_brute_mois(data: LicenciementInput) -> int:
    """
    Calcule l'ancienneté brute en mois (sans préavis).

    Pour licenciement: date_notification - date_entree
    Pour rupture conventionnelle: date_fin_contrat - date_entree
    """
    if data.type_rupture == TypeRupture.LICENCIEMENT and data.date_notification:
        return _calculer_mois_entre_dates(data.date_entree, data.date_notification)
    else:
        return _calculer_mois_entre_dates(data.date_entree, data.date_fin_contrat)


def _calculer_anciennete_totale(data: LicenciementInput) -> int:
    """
    Calcule l'ancienneté totale en mois.

    Pour licenciement: date_fin_contrat - date_entree (inclut le préavis)
    Pour rupture conventionnelle: date_fin_contrat - date_entree
    """
    return _calculer_mois_entre_dates(data.date_entree, data.date_fin_contrat)


def _calculer_anciennete_effective(data: LicenciementInput) -> int:
    """
    Calcule l'ancienneté effective en mois après ajustements.

    - Inclut le préavis pour licenciement
    - Déduit les mois suspendus non comptés
    - Le congé parental temps plein compte pour 50%
    """
    anciennete = _calculer_anciennete_totale(data)

    # Déduire les périodes non comptées
    anciennete -= data.mois_suspendus_non_comptes

    # Le congé parental temps plein compte pour 50%
    # On déduit la moitié (l'autre moitié compte)
    anciennete -= data.mois_conge_parental_temps_plein // 2

    return max(0, anciennete)


def _calculer_coefficient_temps_moyen(data: LicenciementInput) -> Decimal:
    """
    Calcule le coefficient temps moyen pondéré sur toute la carrière.

    Si periodes_travail est vide, on considère temps plein (1.0).
    """
    if not data.periodes_travail:
        return Decimal("1.0")

    total_mois = sum(p.duree_mois for p in data.periodes_travail)
    if total_mois == 0:
        return Decimal("1.0")

    somme_ponderee = sum(
        Decimal(str(p.duree_mois)) * Decimal(str(p.coefficient_temps))
        for p in data.periodes_travail
    )

    return (somme_ponderee / Decimal(str(total_mois))).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


def _calculer_salaire_reference(data: LicenciementInput) -> tuple[Decimal, str]:
    """
    Calcule le salaire de référence selon les deux méthodes légales.

    Retourne le plus favorable et la méthode utilisée.

    Formule A: Moyenne des 12 derniers mois
    Formule B: Moyenne des 3 derniers mois (primes annuelles au prorata 3/12)

    Note: Les salaires sont ceux AVANT la notification, pas pendant le préavis.
    """
    salaires = data.salaires_12_derniers_mois

    # Formule A: moyenne des 12 (ou moins) derniers mois
    moyenne_12 = sum(salaires, Decimal("0")) / Decimal(len(salaires))

    # Formule B: moyenne des 3 derniers mois avec primes au prorata
    if len(salaires) >= 3:
        trois_derniers = salaires[-3:]
        moyenne_3_brute = sum(trois_derniers, Decimal("0")) / Decimal("3")

        # Retirer les primes annuelles des 3 derniers mois et n'en prendre que 3/12
        # Les primes sont déjà incluses dans les salaires, on les ajuste
        primes_proratisees = data.primes_annuelles_3_derniers_mois * Decimal("3") / Decimal("12")
        # On retire le montant total des primes et on ajoute le prorata
        moyenne_3 = moyenne_3_brute - (data.primes_annuelles_3_derniers_mois / Decimal("3")) + (primes_proratisees / Decimal("3"))
    else:
        moyenne_3 = moyenne_12  # Pas assez de mois pour la formule B

    # Retourner le plus favorable
    if moyenne_12 >= moyenne_3:
        return moyenne_12.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "moyenne_12_mois"
    else:
        return moyenne_3.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "moyenne_3_mois"


def _calculer_indemnite_legale(
    salaire_ref: Decimal,
    anciennete_annees: Decimal,
    coefficient_temps: Decimal,
) -> Decimal:
    """
    Calcule l'indemnité légale selon le barème du Code du travail.

    - Jusqu'à 10 ans: 1/4 de mois par année
    - Au-delà de 10 ans: 1/3 de mois par année supplémentaire
    """
    if anciennete_annees <= Decimal("10"):
        indemnite = salaire_ref * anciennete_annees * Decimal("0.25")
    else:
        # 10 premières années à 1/4
        part_10_ans = salaire_ref * Decimal("10") * Decimal("0.25")
        # Années au-delà à 1/3
        annees_sup = anciennete_annees - Decimal("10")
        part_sup = salaire_ref * annees_sup * Decimal("1") / Decimal("3")
        indemnite = part_10_ans + part_sup

    # Appliquer le coefficient temps moyen
    indemnite = indemnite * coefficient_temps

    return indemnite.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _calculer_indemnite_ccn_1966(
    data: LicenciementInput,
    anciennete_mois: int,
    anciennete_annees: Decimal,
    coefficient_temps: Decimal,
) -> tuple[Decimal | None, str | None]:
    """
    Calcule l'indemnité selon la CCN du 15 mars 1966.

    Règles spécifiques:
    - Minimum 2 ans d'ancienneté
    - 1/2 mois par année d'ancienneté
    - Plafond: 6 mois de salaire
    - Base: moyenne des 3 derniers mois uniquement
    - Ne peut dépasser les rémunérations jusqu'à 65 ans
    """
    # Minimum 2 ans (24 mois) pour la CCN 1966
    if anciennete_mois < 24:
        return None, "Ancienneté insuffisante pour la CCN 1966 (minimum 2 ans)"

    # Salaire de référence: moyenne des 3 derniers mois uniquement
    if len(data.salaires_12_derniers_mois) >= 3:
        salaire_ref_ccn = sum(data.salaires_12_derniers_mois[-3:], Decimal("0")) / Decimal("3")
    else:
        salaire_ref_ccn = sum(data.salaires_12_derniers_mois, Decimal("0")) / Decimal(len(data.salaires_12_derniers_mois))

    salaire_ref_ccn = salaire_ref_ccn.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 1/2 mois par année
    indemnite = salaire_ref_ccn * anciennete_annees * Decimal("0.5") * coefficient_temps

    # Plafond 1: 6 mois de salaire
    plafond_6_mois = salaire_ref_ccn * Decimal("6")
    plafond_description = None

    if indemnite > plafond_6_mois:
        indemnite = plafond_6_mois
        plafond_description = "Plafond CCN 1966: 6 mois de salaire"

    # Plafond 2: ne peut dépasser les rémunérations jusqu'à 65 ans
    if data.age_salarie is not None and data.salaire_mensuel_actuel is not None:
        mois_jusqu_65 = max(0, (65 - data.age_salarie) * 12)
        plafond_65_ans = data.salaire_mensuel_actuel * Decimal(str(mois_jusqu_65))

        if indemnite > plafond_65_ans:
            indemnite = plafond_65_ans
            plafond_description = f"Plafond CCN 1966: rémunérations jusqu'à 65 ans ({mois_jusqu_65} mois)"

    return indemnite.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), plafond_description


def calculer_indemnite_licenciement(data: LicenciementInput) -> LicenciementResult:
    """
    Calcule l'indemnité de licenciement ou rupture conventionnelle.

    Pour licenciement:
    - Vérifie le motif (faute grave/lourde = pas d'indemnité)
    - Inclut le préavis dans l'ancienneté (calculé depuis les dates)
    - Double l'indemnité pour inaptitude professionnelle

    Pour rupture conventionnelle:
    - Pas de motif requis
    - Pas de préavis (ancienneté = date fin convenue)
    - Peut inclure un supralégal négocié
    - Même calcul minimum que le licenciement
    """
    type_rupture = data.type_rupture
    preavis_mois = _calculer_preavis_mois(data)

    # Pour licenciement: vérifier le motif
    if type_rupture == TypeRupture.LICENCIEMENT:
        if data.motif is None:
            # Motif requis pour licenciement
            return LicenciementResult(
                type_rupture=type_rupture,
                montant_indemnite=Decimal("0"),
                montant_minimum=Decimal("0"),
                salaire_reference=Decimal("0"),
                methode_salaire_reference="non_applicable",
                anciennete_retenue_mois=0,
                anciennete_retenue_annees=Decimal("0"),
                indemnite_legale=Decimal("0"),
                indemnite_conventionnelle=None,
                multiplicateur=Decimal("1"),
                preavis_mois=0,
                explication="Le motif du licenciement est requis.",
                eligible=False,
                raison_ineligibilite="Motif de licenciement non spécifié.",
            )

        if data.date_notification is None:
            return LicenciementResult(
                type_rupture=type_rupture,
                montant_indemnite=Decimal("0"),
                montant_minimum=Decimal("0"),
                salaire_reference=Decimal("0"),
                methode_salaire_reference="non_applicable",
                anciennete_retenue_mois=0,
                anciennete_retenue_annees=Decimal("0"),
                indemnite_legale=Decimal("0"),
                indemnite_conventionnelle=None,
                multiplicateur=Decimal("1"),
                preavis_mois=0,
                explication="La date de notification est requise pour un licenciement.",
                eligible=False,
                raison_ineligibilite="Date de notification non spécifiée.",
            )

        # Faute grave/lourde = pas d'indemnité
        if data.motif in (MotifLicenciement.FAUTE_GRAVE, MotifLicenciement.FAUTE_LOURDE):
            return LicenciementResult(
                type_rupture=type_rupture,
                montant_indemnite=Decimal("0"),
                montant_minimum=Decimal("0"),
                salaire_reference=Decimal("0"),
                methode_salaire_reference="non_applicable",
                anciennete_retenue_mois=0,
                anciennete_retenue_annees=Decimal("0"),
                indemnite_legale=Decimal("0"),
                indemnite_conventionnelle=None,
                multiplicateur=Decimal("1"),
                preavis_mois=0,
                explication=f"Aucune indemnité de licenciement n'est due en cas de {data.motif.value}.",
                eligible=False,
                raison_ineligibilite=f"Licenciement pour {data.motif.value}: pas de droit à l'indemnité légale.",
            )

    # Calculer l'ancienneté effective
    anciennete_mois = _calculer_anciennete_effective(data)

    # Vérifier l'ancienneté minimale (8 mois pour le droit légal)
    if anciennete_mois < 8:
        return LicenciementResult(
            type_rupture=type_rupture,
            montant_indemnite=Decimal("0"),
            montant_minimum=Decimal("0"),
            salaire_reference=Decimal("0"),
            methode_salaire_reference="non_applicable",
            anciennete_retenue_mois=anciennete_mois,
            anciennete_retenue_annees=Decimal(str(anciennete_mois)) / Decimal("12"),
            indemnite_legale=Decimal("0"),
            indemnite_conventionnelle=None,
            multiplicateur=Decimal("1"),
            preavis_mois=preavis_mois,
            explication="L'ancienneté minimale de 8 mois n'est pas atteinte.",
            eligible=False,
            raison_ineligibilite="Ancienneté insuffisante (minimum 8 mois requis).",
        )

    # Calculer le coefficient temps moyen
    coefficient_temps = _calculer_coefficient_temps_moyen(data)

    # Calculer le salaire de référence
    salaire_ref, methode_sdr = _calculer_salaire_reference(data)

    # Convertir l'ancienneté en années (avec prorata des mois)
    anciennete_annees = (Decimal(str(anciennete_mois)) / Decimal("12")).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )

    # Calculer l'indemnité légale
    indemnite_legale = _calculer_indemnite_legale(salaire_ref, anciennete_annees, coefficient_temps)

    # Calculer l'indemnité conventionnelle si applicable
    indemnite_conv = None
    plafond_description = None

    if data.convention_collective == ConventionCollective.CCN_1966:
        indemnite_conv, plafond_description = _calculer_indemnite_ccn_1966(
            data, anciennete_mois, anciennete_annees, coefficient_temps
        )

    # Déterminer le multiplicateur (x2 pour inaptitude professionnelle, licenciement uniquement)
    multiplicateur = Decimal("1")
    if (
        type_rupture == TypeRupture.LICENCIEMENT
        and data.motif == MotifLicenciement.INAPTITUDE_PROFESSIONNELLE
    ):
        multiplicateur = Decimal("2")

    # Appliquer le principe de faveur pour le minimum
    indemnite_minimum = indemnite_legale
    source_indemnite = "légale"

    if indemnite_conv is not None and indemnite_conv > indemnite_legale:
        indemnite_minimum = indemnite_conv
        source_indemnite = "conventionnelle (CCN 1966)"

    # Appliquer le multiplicateur au minimum
    montant_minimum = (indemnite_minimum * multiplicateur).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # Calculer le montant final
    indemnite_supralegale = Decimal("0")
    if type_rupture == TypeRupture.RUPTURE_CONVENTIONNELLE and data.indemnite_supralegale:
        indemnite_supralegale = data.indemnite_supralegale

    montant_final = montant_minimum + indemnite_supralegale

    # Construire l'explication
    explication_parts = []

    # Type de rupture
    if type_rupture == TypeRupture.LICENCIEMENT:
        motifs_labels = {
            MotifLicenciement.PERSONNEL: "personnel",
            MotifLicenciement.ECONOMIQUE: "économique",
            MotifLicenciement.INAPTITUDE_PROFESSIONNELLE: "inaptitude d'origine professionnelle",
            MotifLicenciement.INAPTITUDE_NON_PROFESSIONNELLE: "inaptitude d'origine non professionnelle",
        }
        explication_parts.append(f"Licenciement pour motif {motifs_labels[data.motif]}.")  # type: ignore
    else:
        explication_parts.append("Rupture conventionnelle.")

    # Dates
    explication_parts.append(f"Date d'entrée: {data.date_entree.strftime('%d/%m/%Y')}.")
    explication_parts.append(f"Date de fin de contrat: {data.date_fin_contrat.strftime('%d/%m/%Y')}.")

    # Préavis (licenciement uniquement)
    if type_rupture == TypeRupture.LICENCIEMENT and preavis_mois > 0:
        explication_parts.append(f"Préavis de {preavis_mois} mois inclus dans l'ancienneté.")

    # Ancienneté
    annees_int = int(anciennete_annees)
    mois_restants = anciennete_mois - (annees_int * 12)
    if mois_restants > 0:
        explication_parts.append(f"Ancienneté retenue: {annees_int} an(s) et {mois_restants} mois.")
    else:
        explication_parts.append(f"Ancienneté retenue: {annees_int} an(s).")

    # Salaire de référence
    methode_label = "moyenne des 12 derniers mois" if methode_sdr == "moyenne_12_mois" else "moyenne des 3 derniers mois"
    explication_parts.append(f"Salaire de référence: {salaire_ref}€ ({methode_label}).")

    # Source de l'indemnité
    explication_parts.append(f"Indemnité {source_indemnite} retenue (principe de faveur).")

    # Multiplicateur (licenciement uniquement)
    if multiplicateur > 1:
        explication_parts.append("Indemnité doublée (inaptitude professionnelle).")

    # Plafond
    if plafond_description:
        explication_parts.append(plafond_description + ".")

    # Montant minimum
    explication_parts.append(f"Montant minimum légal/conventionnel: {montant_minimum}€.")

    # Supralégal (rupture conventionnelle)
    if indemnite_supralegale > 0:
        explication_parts.append(f"Indemnité supralégale négociée: {indemnite_supralegale}€.")
        explication_parts.append(f"Montant total: {montant_final}€.")
    else:
        explication_parts.append(f"Montant de l'indemnité: {montant_final}€.")

    return LicenciementResult(
        type_rupture=type_rupture,
        montant_indemnite=montant_final,
        montant_minimum=montant_minimum,
        salaire_reference=salaire_ref,
        methode_salaire_reference=methode_sdr,
        anciennete_retenue_mois=anciennete_mois,
        anciennete_retenue_annees=anciennete_annees,
        indemnite_legale=(indemnite_legale * multiplicateur).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        indemnite_conventionnelle=(indemnite_conv * multiplicateur).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if indemnite_conv else None,
        multiplicateur=multiplicateur,
        preavis_mois=preavis_mois,
        indemnite_supralegale=indemnite_supralegale,
        plafond_applique=plafond_description is not None,
        plafond_description=plafond_description,
        explication=" ".join(explication_parts),
        eligible=True,
        raison_ineligibilite=None,
    )
