"""
routes.py - Aggregated API v1 Router
"""
from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.nodes import router as nodes_router
from app.api.v1.servers import router as servers_router
from app.api.v1.modpacks import router as modpacks_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(nodes_router)
api_router.include_router(servers_router)
api_router.include_router(modpacks_router)
