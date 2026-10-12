from fastapi import APIRouter, Depends

from app.api.v1 import admin_users, auth, vehicles
from app.auth.dependencies import verify_csrf

# Every state-changing /api/v1 call needs the CSRF header. The partner API (NA-05) lives on its own router.
api_router = APIRouter(dependencies=[Depends(verify_csrf)])
api_router.include_router(auth.router)
api_router.include_router(auth.me_router)
api_router.include_router(vehicles.router)
api_router.include_router(admin_users.router)
