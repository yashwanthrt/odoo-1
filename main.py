from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Literal

from odoo_service import OdooService

app = FastAPI()

# -----------------------
# CORS (important for frontend)
# -----------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------
# Odoo Service
# -----------------------
odoo_service = OdooService()

# -----------------------
# Database Setup
# -----------------------
DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

Base = declarative_base()

# -----------------------
# DB Model
# -----------------------
class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

Base.metadata.create_all(bind=engine)

# -----------------------
# Schemas
# -----------------------
class ItemCreate(BaseModel):
    name: str

class ItemResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class PartnerCreate(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    company_type: Optional[Literal["person", "company"]] = "person"
    vat: Optional[str] = None
    role: Optional[Literal["customer", "vendor", "all"]] = "customer"


class PartnerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    company_type: Optional[Literal["person", "company"]] = None
    vat: Optional[str] = None
    role: Optional[Literal["customer", "vendor", "all"]] = None


# -----------------------
# DB Dependency
# -----------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------
# Local APIs
# -----------------------
@app.post("/items/", response_model=ItemResponse)
def create_item(item: ItemCreate, db: Session = Depends(get_db)):
    db_item = Item(name=item.name)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@app.get("/items/", response_model=List[ItemResponse])
def get_items(db: Session = Depends(get_db)):
    return db.query(Item).all()


# -----------------------
# Odoo APIs (NOW SHOW REAL ERRORS)
# -----------------------
@app.get("/odoo/partners")
def get_odoo_partners(role: Literal["customer", "vendor", "all"] = "customer", limit: int = 100):
    try:
        return odoo_service.get_partners(role=role, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/odoo/customers")
def get_odoo_customers(limit: int = 100):
    try:
        return odoo_service.get_customers(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/odoo/partners")
def create_odoo_partner(partner: PartnerCreate):
    try:
        return odoo_service.create_partner(
            partner.model_dump(exclude_none=True)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/odoo/partners/{partner_id}")
def update_odoo_partner(partner_id: int, partner: PartnerUpdate):
    try:
        return odoo_service.update_partner(
            partner_id,
            partner.model_dump(exclude_none=True)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/odoo/partners/{partner_id}")
def delete_odoo_partner(partner_id: int):
    try:
        return odoo_service.delete_partner(partner_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/odoo/auth-verify")
def verify_odoo_auth():
    try:
        return odoo_service.verify_auth()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------
# DEBUG (VERY IMPORTANT)
# -----------------------
@app.get("/debug-env")
def debug_env():
    import os
    return {
        "url": os.getenv("ODOO_URL"),
        "db": os.getenv("ODOO_DB"),
        "user": os.getenv("ODOO_USERNAME"),
        "password_exists": bool(os.getenv("ODOO_PASSWORD"))
    }
