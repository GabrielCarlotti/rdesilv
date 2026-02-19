"""API router principal."""

from fastapi import APIRouter

from src.app.routes.extract import router as extract_router
from src.app.routes.check import router as check_router
from src.app.routes.licenciement import router as licenciement_router

router = APIRouter()

router.include_router(extract_router, tags=["extract"])
router.include_router(check_router, tags=["check"])
router.include_router(licenciement_router, tags=["licenciement"])
