"""Owner: Moinul. Replace placeholders with reviewed implementation."""
from fastapi import APIRouter

router = APIRouter(prefix="/results", tags=["results"])

from app.results.audit_api import router as audit_router
router.include_router(audit_router)

from app.results.count_api import router as count_router
router.include_router(count_router)

from app.results.publish_api import router as publication_router
router.include_router(publication_router)

from app.results.read_api import router as read_router
router.include_router(read_router)
