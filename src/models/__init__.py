"""Models package."""

from .payslip import (
    FichePayeExtracted,
    EmployerInfo,
    EmployeeInfo,
    PayPeriod,
    PayslipLine,
    PayslipTotals,
    LeaveBalance,
)
from .check import (
    CheckResult,
    CheckReport,
)
from .frappe import (
    FrappeCheckInput,
    FrappeCheckOutput,
    FrappeError,
)
from .licenciement import (
    TypeRupture,
    MotifLicenciement,
    ConventionCollective,
    PeriodeTravail,
    LicenciementInput,
    LicenciementResult,
    SalaireMensuel,
    LicenciementPdfExtraction,
)
from .convention_check import (
    ConventionWarning,
    ConventionCheckOutput,
)

__all__ = [
    "FichePayeExtracted",
    "EmployerInfo",
    "EmployeeInfo",
    "PayPeriod",
    "PayslipLine",
    "PayslipTotals",
    "LeaveBalance",
    "CheckResult",
    "CheckReport",
    "FrappeCheckInput",
    "FrappeCheckOutput",
    "FrappeError",
    "TypeRupture",
    "MotifLicenciement",
    "ConventionCollective",
    "PeriodeTravail",
    "LicenciementInput",
    "LicenciementResult",
    "SalaireMensuel",
    "LicenciementPdfExtraction",
    "ConventionWarning",
    "ConventionCheckOutput",
]
