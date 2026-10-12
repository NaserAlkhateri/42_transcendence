from fastapi import APIRouter

from app.api.v1 import vehicles

api_router = APIRouter()
api_router.include_router(vehicles.router)
