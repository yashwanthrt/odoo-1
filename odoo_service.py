import os
import json
import xmlrpc.client
from fastapi import HTTPException

try:
    from dotenv import load_dotenv
    load_dotenv()
except ModuleNotFoundError:
    pass


# -----------------------
# Config
# -----------------------
class Config:
    @staticmethod
    def get():
        url = (os.getenv("ODOO_URL") or "").strip()
        db = (os.getenv("ODOO_DB") or "").strip()
        username = (os.getenv("ODOO_USERNAME") or "").strip()
        password = (os.getenv("ODOO_PASSWORD") or "").strip()

        if url and db and username and password:
            return url, db, username, password

        # fallback to config.json
        try:
            with open("config.json") as f:
                data = json.load(f)
                return (
                    data["ODOO_URL"].strip(),
                    data["ODOO_DB"].strip(),
                    data["ODOO_USERNAME"].strip(),
                    data["ODOO_PASSWORD"].strip(),
                )
        except Exception:
            raise RuntimeError("Odoo configuration not found")


ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD = Config.get()


# -----------------------
# Service
# -----------------------
class OdooService:
    def __init__(self):
        self.url = ODOO_URL.rstrip("/")
        self.db = ODOO_DB
        self.username = ODOO_USERNAME
        self.password = ODOO_PASSWORD

        self._uid = None

        self._common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
        self._models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")

    # -----------------------
    # Auth (cached)
    # -----------------------
    def authenticate(self):
        if self._uid:
            return self._uid

        uid = self._common.authenticate(
            self.db,
            self.username,
            self.password,
            {}
        )

        if not uid:
            raise HTTPException(status_code=401, detail="Odoo authentication failed")

        self._uid = uid
        return uid

    # -----------------------
    def _normalize_role(self, role: str):
        role = role.strip().lower()
        if role.endswith("s"):
            role = role[:-1]

        if role not in ["customer", "vendor", "all"]:
            raise HTTPException(status_code=400, detail="Invalid role")

        return role

    # -----------------------
    def get_partners(self, role="customer", limit=100):
        uid = self.authenticate()
        role = self._normalize_role(role)
        except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

        if role == "vendor":
            domain = [["supplier_rank", ">", 0]]
        elif role == "all":
            domain = ['|', ["customer_rank", ">", 0], ["supplier_rank", ">", 0]]
        else:
            domain = [["customer_rank", ">", 0]]

        ids = self._models.execute_kw(
            self.db, uid, self.password,
            "res.partner", "search",
            [domain], {"limit": limit}
        )

        if not ids:
            return []

        return self._models.execute_kw(
            self.db, uid, self.password,
            "res.partner", "read",
            [ids],
            {"fields": ["id", "name", "email", "phone", "mobile", "company_type", "vat"]}
        )

    # -----------------------
    def create_partner(self, data):
        uid = self.authenticate()

        role = data.pop("role", "customer")

        if role == "customer":
            data["customer_rank"] = 1
        elif role == "vendor":
            data["supplier_rank"] = 1
        elif role == "all":
            data["customer_rank"] = 1
            data["supplier_rank"] = 1

        partner_id = self._models.execute_kw(
            self.db, uid, self.password,
            "res.partner", "create",
            [data]
        )

        return {"id": partner_id}

    # -----------------------
    def update_partner(self, partner_id, data):
        uid = self.authenticate()

        if not data:
            raise HTTPException(status_code=400, detail="No data to update")

        role = data.pop("role", None)

        if role:
            if role == "customer":
                data["customer_rank"] = 1
            elif role == "vendor":
                data["supplier_rank"] = 1
            elif role == "all":
                data["customer_rank"] = 1
                data["supplier_rank"] = 1

        self._models.execute_kw(
            self.db, uid, self.password,
            "res.partner", "write",
            [[partner_id], data]
        )

        return {"updated": True}

    # -----------------------
    def delete_partner(self, partner_id):
        uid = self.authenticate()

        self._models.execute_kw(
            self.db, uid, self.password,
            "res.partner", "unlink",
            [[partner_id]]
        )

        return {"deleted": True}

    # -----------------------
    def get_customers(self, limit=100):
        return self.get_partners("customer", limit)

    # -----------------------
    def verify_auth(self):
        uid = self.authenticate()
        return {"authenticated": True, "uid": uid}
