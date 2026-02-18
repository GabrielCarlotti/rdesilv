"""
Extracteur de fiches de paie PDF.

Extrait le texte et les tables des bulletins de salaire PDF
et les structure dans un modèle Pydantic.
"""

import re
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

# Ajouter le répertoire src au path pour les imports directs
_src_path = Path(__file__).parent.parent
if str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))

import pdfplumber

from models.payslip import (
    EmployeeInfo,
    EmployerInfo,
    FichePayeExtracted,
    LeaveBalance,
    PayPeriod,
    PayslipLine,
    PayslipTotals,
)


def parse_decimal(value: str | None) -> Decimal | None:
    """Parse une chaîne en Decimal, retourne None si impossible."""
    if not value:
        return None
    try:
        # Nettoyage: enlever espaces, remplacer virgule par point
        cleaned = value.strip().replace(" ", "").replace(",", ".").replace("\xa0", "")
        # Enlever le signe négatif entre parenthèses style comptable
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        if not cleaned or cleaned == "-":
            return None
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def parse_date_fr(value: str | None) -> date | None:
    """Parse une date au format français (dd/mm/yyyy)."""
    if not value:
        return None
    try:
        # Format: dd/mm/yyyy
        match = re.search(r"(\d{2})/(\d{2})/(\d{4})", value)
        if match:
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return date(year, month, day)
    except (ValueError, AttributeError):
        pass
    return None


class PayslipExtractor:
    """
    Extracteur de fiches de paie PDF.

    Utilise pdfplumber pour extraire:
    - Le texte brut de chaque page
    - Les tables structurées

    Puis parse ces données dans un modèle Pydantic FichePayeExtracted.
    """

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"Fichier introuvable : {self.pdf_path}")
        if self.pdf_path.suffix.lower() != ".pdf":
            raise ValueError(f"Le fichier doit être un PDF : {self.pdf_path}")

        self._raw_text: str = ""
        self._raw_tables: list[list[list[Any]]] = []
        self._errors: list[str] = []

    def extract(self) -> FichePayeExtracted:
        """
        Extrait et parse le bulletin de paie complet.

        Returns:
            FichePayeExtracted: Le modèle structuré avec toutes les données.
        """
        self._extract_raw_content()
        return self._parse_to_model()

    def _extract_raw_content(self) -> None:
        """Extrait le texte brut et les tables du PDF."""
        text_parts: list[str] = []
        tables: list[list[list[Any]]] = []

        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Extraction du texte
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                except Exception as e:
                    self._errors.append(f"Erreur extraction texte page {page_num + 1}: {e}")

                # Extraction des tables
                try:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
                except Exception as e:
                    self._errors.append(f"Erreur extraction tables page {page_num + 1}: {e}")

        self._raw_text = "\n\n".join(text_parts)
        self._raw_tables = tables

    def _parse_to_model(self) -> FichePayeExtracted:
        """Parse le contenu extrait dans le modèle Pydantic."""
        result = FichePayeExtracted(
            source_file=str(self.pdf_path),
            extraction_errors=self._errors,
        )

        # Parser les différentes sections
        self._parse_employer_info(result)
        self._parse_employee_info(result)
        self._parse_period_info(result)
        self._parse_payslip_lines(result)
        self._parse_totals(result)
        self._parse_leave_balance(result)

        result.extraction_success = len(self._errors) == 0 or len(result.lignes) > 0

        return result

    def _parse_employer_info(self, result: FichePayeExtracted) -> None:
        """Parse les informations employeur."""
        text = self._raw_text
        employer = EmployerInfo()

        # Entreprise
        match = re.search(r"Entreprise\s*:\s*([^\n]+)", text, re.IGNORECASE)
        if match:
            employer.entreprise = match.group(1).strip()

        # Etablissement
        match = re.search(r"Etablissement\s*:\s*([^\n]+)", text, re.IGNORECASE)
        if match:
            employer.etablissement = match.group(1).strip()

        # SIRET
        match = re.search(r"Siret\s*:\s*(\w+)", text, re.IGNORECASE)
        if match:
            employer.siret = match.group(1).strip()

        # APE
        match = re.search(r"APE\s*:\s*(\w+)", text, re.IGNORECASE)
        if match:
            employer.ape = match.group(1).strip()

        # URSSAF
        match = re.search(r"URSSAF\s*:\s*([^\n]+)", text, re.IGNORECASE)
        if match:
            employer.urssaf = match.group(1).strip()

        # N° cotisant
        match = re.search(r"N°\s*de\s*cotisant\s*:\s*(\d+)", text, re.IGNORECASE)
        if match:
            employer.numero_cotisant = match.group(1).strip()

        # Convention collective
        match = re.search(r"Convention\s+Collective\s+([^\n]+)", text, re.IGNORECASE)
        if match:
            employer.convention_collective = match.group(1).strip()

        result.employeur = employer

    def _parse_employee_info(self, result: FichePayeExtracted) -> None:
        """Parse les informations employé."""
        text = self._raw_text
        employee = EmployeeInfo()

        # Matricule
        match = re.search(r"Matricule\s*:\s*(\d+)", text, re.IGNORECASE)
        if match:
            employee.matricule = match.group(1).strip()

        # N° sécurité sociale
        match = re.search(r"N°\s*de\s*sécurité\s*sociale\s*:\s*([\d\s]+)", text, re.IGNORECASE)
        if match:
            employee.numero_securite_sociale = match.group(1).strip().replace(" ", "")

        # Date d'entrée
        match = re.search(r"Date\s*d'entrée\s*:\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
        if match:
            employee.date_entree = parse_date_fr(match.group(1))

        # Qualification
        match = re.search(r"Qualification\s+Conventionnelle\s*:\s*([^\n]+?)(?:N°|$)", text, re.IGNORECASE)
        if match:
            employee.qualification = match.group(1).strip()

        # Emploi
        match = re.search(r"Emploi\s*:\s*([^\n]+?)(?:Echelon|$)", text, re.IGNORECASE)
        if match:
            employee.emploi = match.group(1).strip()

        # Echelon
        match = re.search(r"Echelon\s*:\s*([^\n]+)", text, re.IGNORECASE)
        if match:
            employee.echelon = match.group(1).strip()

        # Coefficient
        match = re.search(r"Coefficient\s*:\s*([\d,\.]+)", text, re.IGNORECASE)
        if match:
            employee.coefficient = parse_decimal(match.group(1))

        # Nom complet - on cherche "Mme" ou "M." suivi du nom
        match = re.search(r"(Mme|M\.|Mr|Mlle)\s+([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s]+)\s+([A-Za-zàâäéèêëïîôùûüçÀÂÄÉÈÊËÏÎÔÙÛÜÇ]+)", text)
        if match:
            employee.nom = match.group(2).strip()
            employee.prenom = match.group(3).strip()
            employee.nom_complet = f"{match.group(1)} {match.group(2).strip()} {match.group(3).strip()}"

        # Adresse employé - chercher après le nom
        match = re.search(r"\d+\s*[A-Z]?\s*RUE\s+[^\n]+", text, re.IGNORECASE)
        if match:
            employee.adresse = match.group(0).strip()

        # Catégorie (Cadre, Non-cadre)
        if re.search(r"\bCADRE\b", text, re.IGNORECASE):
            employee.categorie = "Cadre"

        result.employe = employee

    def _parse_period_info(self, result: FichePayeExtracted) -> None:
        """Parse les informations de période."""
        text = self._raw_text
        period = PayPeriod()

        # Période du/au
        match = re.search(r"Période\s*:\s*du\s*(\d{2}/\d{2}/\d{4})\s*au\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
        if match:
            period.date_debut = parse_date_fr(match.group(1))
            period.date_fin = parse_date_fr(match.group(2))
            if period.date_fin:
                period.mois = period.date_fin.month
                period.annee = period.date_fin.year

        # Numéro de bulletin
        match = re.search(r"Bulletin\s*n°\s*:\s*(\d+)", text, re.IGNORECASE)
        if match:
            period.numero_bulletin = match.group(1).strip()

        result.periode = period

    def _parse_payslip_lines(self, result: FichePayeExtracted) -> None:
        """Parse les lignes de cotisations depuis les tables."""
        lignes_dict: dict[str, PayslipLine] = {}
        lignes_list: list[PayslipLine] = []

        for table in self._raw_tables:
            for row in table:
                if not row or len(row) < 3:
                    continue

                # Chercher des lignes qui commencent par un numéro (5 chiffres typiquement)
                first_cell = str(row[0] or "").strip()
                if not re.match(r"^\d{4,5}$", first_cell):
                    continue

                try:
                    line = self._parse_single_line(row)
                    if line:
                        if line.numero:
                            lignes_dict[line.numero] = line
                        lignes_list.append(line)
                except Exception as e:
                    self._errors.append(f"Erreur parsing ligne {first_cell}: {e}")

        result.lignes = lignes_dict
        result.lignes_liste = lignes_list

    def _parse_single_line(self, row: list[Any]) -> PayslipLine | None:
        """Parse une ligne de cotisation individuelle."""
        # Structure typique: [N°, None, Libellé, Base, None, Taux Sal, Montant Sal, Taux Pat, Montant Pat]
        # Index:              0    1     2        3     4     5          6            7          8

        if len(row) < 3:
            return None

        numero = str(row[0] or "").strip()
        if not numero:
            return None

        # Trouver le libellé (généralement en position 2)
        libelle = ""
        for cell in row[1:4]:
            if cell and str(cell).strip():
                cell_str = str(cell).strip()
                # Vérifier que ce n'est pas juste un nombre
                cleaned = cell_str.replace(",", ".").replace("-", "").replace(" ", "").replace(".", "")
                if not cleaned.isdigit():
                    libelle = cell_str
                    break

        if not libelle:
            return None

        # Initialiser les valeurs
        base = None
        taux_sal = None
        montant_sal = None
        taux_pat = None
        montant_pat = None

        # Parser selon la structure à 9 colonnes
        if len(row) >= 9:
            # Colonne 3: Base
            if row[3]:
                base = parse_decimal(str(row[3]))

            # Colonne 5: Taux salarial
            if row[5]:
                taux_sal = parse_decimal(str(row[5]))

            # Colonne 6: Montant salarial (peut être négatif = retenue, ou positif = gain)
            if row[6]:
                montant_sal = parse_decimal(str(row[6]))

            # Colonne 7: Taux patronal
            if row[7]:
                taux_pat = parse_decimal(str(row[7]))

            # Colonne 8: Montant patronal
            if row[8]:
                montant_pat = parse_decimal(str(row[8]))

        return PayslipLine(
            numero=numero,
            libelle=libelle,
            base=base,
            taux_salarial=taux_sal,
            montant_salarial=montant_sal,
            taux_patronal=taux_pat,
            montant_patronal=montant_pat,
        )

    def _parse_totals(self, result: FichePayeExtracted) -> None:
        """Parse les totaux et cumuls."""
        text = self._raw_text
        totaux = PayslipTotals()

        # Brut soumis à cotisation
        match = re.search(r"Brut\s+soumis\s+à\s+cotisation.*?([\d\s,\.]+)", text, re.IGNORECASE)
        if match:
            totaux.salaire_brut = parse_decimal(match.group(1))

        # Chercher dans les lignes aussi
        for line in result.lignes_liste:
            if "brut soumis" in line.libelle.lower():
                totaux.salaire_brut = line.montant_salarial or line.base
            elif "net à payer" in line.libelle.lower() and "avant" in line.libelle.lower():
                totaux.net_avant_impot = line.montant_salarial
            elif "net social" in line.libelle.lower():
                totaux.net_social = line.montant_salarial
            elif "prélèvement à la source" in line.libelle.lower():
                totaux.montant_pas = line.montant_salarial
                totaux.taux_pas = line.taux_salarial

        # Net à payer final
        match = re.search(r"Net\s+à\s+payer\s+([\d\s,\.]+)\s*Euros", text, re.IGNORECASE)
        if match:
            totaux.net_a_payer = parse_decimal(match.group(1))

        # Cumuls
        match = re.search(r"Cumul\s+Brut\s+([\d\s,\.]+)", text, re.IGNORECASE)
        if match:
            totaux.cumul_brut = parse_decimal(match.group(1))

        match = re.search(r"Cumul\s+Heures\s+([\d\s,\.]+)", text, re.IGNORECASE)
        if match:
            totaux.cumul_heures = parse_decimal(match.group(1))

        match = re.search(r"Cumul\s+Net\s+Imposable\s+([\d\s,\.]+)", text, re.IGNORECASE)
        if match:
            totaux.cumul_net_imposable = parse_decimal(match.group(1))

        match = re.search(r"Net\s+Imposable\s+mensuel\s+([\d\s,\.]+)", text, re.IGNORECASE)
        if match:
            totaux.net_imposable = parse_decimal(match.group(1))

        # Mode de paiement
        match = re.search(r"réglé\s+le\s*:\s*(\d{2}/\d{2}/\d{4})\s+par\s*:\s*(\w+)", text, re.IGNORECASE)
        if match:
            totaux.date_paiement = parse_date_fr(match.group(1))
            totaux.mode_paiement = match.group(2).strip()

        # IBAN
        match = re.search(r"([A-Z]{2}\d{2}[A-Z0-9]{10,30})", text)
        if match:
            totaux.iban = match.group(1)

        # Type de taux PAS
        if "Taux Personnalisé" in text:
            totaux.type_taux_pas = "Personnalisé"
        elif "Taux Neutre" in text:
            totaux.type_taux_pas = "Neutre"

        result.totaux = totaux

    def _parse_leave_balance(self, result: FichePayeExtracted) -> None:
        """Parse les soldes de congés."""
        text = self._raw_text
        conges = LeaveBalance()

        # SOLDE congés N
        match = re.search(r"SOLDE\s+congés\s+\d+/\d+\s+N\s+([\d,\.]+)", text, re.IGNORECASE)
        if match:
            conges.conges_n = parse_decimal(match.group(1))

        # SOLDE congés N-1
        match = re.search(r"SOLDE\s+congés\s+\d+/\d+\s+N-1\s+([\d,\.]+)", text, re.IGNORECASE)
        if match:
            conges.conges_n1 = parse_decimal(match.group(1))

        # SOLDE congés N-2
        match = re.search(r"SOLDE\s+congés\s+\d+/\d+\s+N-2\s+([\d,\.]+)", text, re.IGNORECASE)
        if match:
            conges.conges_n2 = parse_decimal(match.group(1))

        result.conges = conges


def extract_payslip(pdf_path: str | Path) -> FichePayeExtracted:
    """
    Fonction utilitaire pour extraire une fiche de paie.

    Args:
        pdf_path: Chemin vers le fichier PDF.

    Returns:
        FichePayeExtracted: Les données structurées extraites.
    """
    extractor = PayslipExtractor(pdf_path)
    return extractor.extract()


def extract_payslips_from_directory(
    directory: str | Path,
    pattern: str = "*.pdf"
) -> list[FichePayeExtracted]:
    """
    Extrait toutes les fiches de paie d'un répertoire.

    Args:
        directory: Chemin vers le répertoire contenant les PDFs.
        pattern: Pattern glob pour filtrer les fichiers (défaut: *.pdf).

    Returns:
        Liste des fiches de paie extraites.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        raise FileNotFoundError(f"Répertoire introuvable : {dir_path}")

    results = []
    for pdf_file in sorted(dir_path.glob(pattern)):
        try:
            result = extract_payslip(pdf_file)
            results.append(result)
        except Exception as e:
            # Créer un résultat d'erreur pour ce fichier
            results.append(FichePayeExtracted(
                source_file=str(pdf_file),
                extraction_success=False,
                extraction_errors=[str(e)],
            ))

    return results


if __name__ == "__main__":
    import json

    path = sys.argv[1] if len(sys.argv) > 1 else "/Users/gabrielcarlotti/Dev/esilv/rdesilv/data/Erreur Détaillée split/bulletin_en_erreur_Version_détaillée-2.pdf"

    result = extract_payslip(path)

    # Afficher en JSON formaté
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
