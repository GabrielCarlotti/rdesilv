"""Application FastAPI principale."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.app.api import router

app = FastAPI(
    title="Extracteur de Fiches de Paie",
    description="API pour extraire les données des bulletins de salaire PDF",
    version="0.1.0",
)
app.add_middleware(
      CORSMiddleware,
      allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
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
