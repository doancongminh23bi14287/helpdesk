from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.item import Item, PriceList, PriceListItem
from app.models.user import User
from app.core.deps import get_current_user, require_admin
from app.schemas.item import (
    PriceListCreate, PriceListOut, PriceListWithItems,
    PriceListItemCreate, PriceListItemUpdate, PriceListItemOut,
)

router = APIRouter(prefix="/api/price-lists", tags=["price_lists"])


@router.get("", response_model=List[PriceListOut])
def list_price_lists(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return db.query(PriceList).filter(PriceList.is_active.is_(True)).all()


@router.post("", response_model=PriceListOut)
def create_price_list(
    payload: PriceListCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    pl = PriceList(**payload.model_dump())
    db.add(pl)
    db.commit()
    db.refresh(pl)
    return pl


@router.get("/{pl_id}", response_model=PriceListWithItems)
def get_price_list(
    pl_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pl = db.query(PriceList).filter(PriceList.id == pl_id).first()
    if not pl:
        raise HTTPException(status_code=404, detail="Price list not found")
    pli_rows = db.query(PriceListItem).filter(PriceListItem.price_list_id == pl_id).all()
    item_ids = [pli.item_id for pli in pli_rows]
    item_map = {}
    if item_ids:
        items = db.query(Item).filter(Item.id.in_(item_ids)).all()
        item_map = {i.id: i for i in items}
    return PriceListWithItems(
        id=pl.id,
        name=pl.name,
        currency=pl.currency,
        is_active=pl.is_active,
        created_at=pl.created_at,
        items=[
            PriceListItemOut(
                id=pli.id,
                price_list_id=pli.price_list_id,
                item_id=pli.item_id,
                unit_price=pli.unit_price,
                item=item_map.get(pli.item_id),
            )
            for pli in pli_rows
        ],
    )


@router.post("/{pl_id}/items", response_model=PriceListItemOut)
def add_item_to_price_list(
    pl_id: int,
    payload: PriceListItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    pl = db.query(PriceList).filter(PriceList.id == pl_id).first()
    if not pl:
        raise HTTPException(status_code=404, detail="Price list not found")
    item = db.query(Item).filter(Item.id == payload.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    existing = db.query(PriceListItem).filter(
        PriceListItem.price_list_id == pl_id,
        PriceListItem.item_id == payload.item_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Item already in price list")
    pli = PriceListItem(price_list_id=pl_id, **payload.model_dump())
    db.add(pli)
    db.commit()
    db.refresh(pli)
    return pli


@router.put("/{pl_id}/items/{item_id}", response_model=PriceListItemOut)
def update_price_list_item(
    pl_id: int,
    item_id: int,
    payload: PriceListItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    pli = db.query(PriceListItem).filter(
        PriceListItem.price_list_id == pl_id,
        PriceListItem.item_id == item_id,
    ).first()
    if not pli:
        raise HTTPException(status_code=404, detail="Item not in price list")
    pli.unit_price = payload.unit_price
    db.commit()
    db.refresh(pli)
    return pli


@router.delete("/{pl_id}/items/{item_id}", status_code=204)
def remove_item_from_price_list(
    pl_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    pli = db.query(PriceListItem).filter(
        PriceListItem.price_list_id == pl_id,
        PriceListItem.item_id == item_id,
    ).first()
    if not pli:
        raise HTTPException(status_code=404, detail="Item not in price list")
    db.delete(pli)
    db.commit()
