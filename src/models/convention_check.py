"""Modèles pour le check de cohérence avec la convention collective via LLM."""

from pydantic import BaseModel, Field


class ConventionWarning(BaseModel):
    """Un avertissement de cohérence avec la convention collective."""

    categorie: str = Field(
        ...,
        description="Catégorie de l'avertissement (ex: 'remuneration', 'anciennete', 'conges', 'cotisations', 'autre')"
    )
    titre: str = Field(
        ...,
        description="Titre court de l'avertissement (ex: 'Majoration ancienneté potentiellement incorrecte')"
    )
    description: str = Field(
        ...,
        description="Description détaillée de l'incohérence potentielle détectée"
    )
    article_convention: str | None = Field(
        default=None,
        description="Référence à l'article de la convention collective concerné (ex: 'Article 39')"
    )
    severite: str = Field(
        default="info",
        description="Niveau de sévérité: 'info' (à vérifier), 'attention' (incohérence probable), 'important' (incohérence certaine)"
    )


class ConventionCheckOutput(BaseModel):
    """Sortie du LLM pour le check de cohérence convention collective."""

    warnings: list[ConventionWarning] = Field(
        default_factory=list,
        description="Liste des avertissements détectés. Vide si aucune incohérence."
    )
    analyse_effectuee: bool = Field(
        default=True,
        description="True si l'analyse a pu être effectuée correctement"
    )
    resume: str = Field(
        default="",
        description="Résumé court de l'analyse (1-2 phrases)"
    )
