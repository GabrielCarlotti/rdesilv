"""Application FastAPI principale."""

from fastapi import FastAPI

from src.app.api import router

app = FastAPI(
    title="Extracteur de Fiches de Paie",
    description="API pour extraire les données des bulletins de salaire PDF",
    version="0.1.0",
)

app.include_router(router, prefix="/api", tags=["traitement"])


def dev_server():
    """Lance le serveur de développement."""
    import uvicorn
    uvicorn.run("src.app.main:app", host="0.0.0.0", port=8000, reload=True)


def prod_server():
    """Lance le serveur de production."""
    import uvicorn
    uvicorn.run("src.app.main:app", host="0.0.0.0", port=8000, workers=4)
