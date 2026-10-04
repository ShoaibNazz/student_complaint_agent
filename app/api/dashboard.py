from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import AdminUser, get_current_admin
from app.database.database import get_db
from app.models.enums import ComplaintStatus, Priority
from app.schemas.complaint import DashboardStats
from app.services import complaint_service as svc
from app.services.category_service import get_catalog
from app.services.routing_service import get_routing_service

router = APIRouter(prefix="/api", tags=["dashboard & configuration"])


@router.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db), _: AdminUser = Depends(get_current_admin)):
    return svc.get_dashboard_stats(db)


@router.get("/categories")
def categories():
    catalog = get_catalog()
    return [{"name": n, "description": catalog.get(n).description, "subcategories": catalog.subcategory_names(n)}
            for n in catalog.names]


@router.get("/departments")
def departments():
    return [{"name": n} for n in get_routing_service().department_names]


@router.get("/meta", include_in_schema=False)
def meta():
    return {"priorities": [p.value for p in Priority], "statuses": [s.value for s in ComplaintStatus]}
