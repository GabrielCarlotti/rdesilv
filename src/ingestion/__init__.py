"""Module d'ingestion des fiches de paie PDF."""

from .ingestion import (
    PayslipExtractor,
    extract_payslip,
    extract_payslips_from_directory,
)

__all__ = [
    "PayslipExtractor",
    "extract_payslip",
    "extract_payslips_from_directory",
]
