from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional, Union
from math import ceil
from app.database import get_db
from app.models.item import Item, PriceList, PriceListItem
from app.models.organization import Organization
from app.models.user import User
from app.core.deps import get_current_user, require_admin
from app.schemas.item import ItemCreate, ItemUpdate, ItemOut

router = APIRouter(prefix="/api/items", tags=["items"])

VALID_ITEM_SORT_FIELDS = {"code", "name", "type", "unit_price", "created_at"}


@router.get("")
def list_items(
    search: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    paginated: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Item)
    # If no pagination/search params requested, return flat list for backwards compat (active only)
    if not paginated and search is None and type is None and is_active is None:
        return q.filter(Item.is_active.is_(True)).all()
    # Apply is_active filter: explicit param takes precedence; paginated mode with no param returns all
    if is_active is not None:
        q = q.filter(Item.is_active == is_active)
    elif not paginated:
        # Non-paginated but with other filters: still restrict to active
        q = q.filter(Item.is_active.is_(True))
    # Paginated path
    if type:
        q = q.filter(Item.type == type)
    if search:
        term = f"%{search}%"
        q = q.filter(or_(Item.code.ilike(term), Item.name.ilike(term)))
    if sort not in VALID_ITEM_SORT_FIELDS:
        sort = "created_at"
    sort_col = getattr(Item, sort, Item.created_at)
    q = q.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": ceil(total / per_page) if total > 0 else 1,
    }


@router.get("/lookup")
def lookup_items(
    org_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return items with prices resolved for the org's price list."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if user.role == "customer" and user.org_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    items = db.query(Item).filter(Item.is_active.is_(True)).all()

    # Pre-fetch all price list item overrides in one query
    price_overrides = {}
    if org.price_list_id:
        pli_rows = db.query(PriceListItem).filter(
            PriceListItem.price_list_id == org.price_list_id
        ).all()
        price_overrides = {pli.item_id: pli.unit_price for pli in pli_rows}

    result = []
    for item in items:
        price = price_overrides.get(item.id, item.unit_price)
        result.append({
            "id": item.id,
            "code": item.code,
            "name": item.name,
            "type": item.type,
            "unit_price": float(price),
            "unit": item.unit,
        })
    return result


@router.get("/{item_id}", response_model=ItemOut)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("", response_model=ItemOut)
def create_item(
    payload: ItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    if db.query(Item).filter(Item.code == payload.code).first():
        raise HTTPException(status_code=409, detail="Item code already exists")
    item = Item(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{item_id}", response_model=ItemOut)
def update_item(
    item_id: int,
    payload: ItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item
