from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, date
import jwt
import bcrypt
from enum import Enum
import csv
import io
from openpyxl import Workbook, load_workbook
from dateutil import parser as date_parser
import pytz

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Environment variables
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']
JWT_SECRET = os.environ.get('JWT_SECRET', 'finrealty-secret-key-2024')
TIMEZONE = pytz.timezone('America/Tijuana')

# MongoDB connection
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(
    title="FinRealty API",
    version="1.0.0",
    description="Sistema de Control Financiero para Desarrollos Inmobiliarios",
    docs_url="/docs",
    redoc_url="/redoc"
)
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# Root health check
@app.get("/")
async def root():
    return {"status": "ok", "service": "FinRealty API", "version": "1.0.0"}

@app.get("/api/health")
async def api_health():
    return {"status": "ok", "api": "up"}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========================= ENUMS =========================
class UserRole(str, Enum):
    ADMIN = "admin"
    FINANZAS = "finanzas"
    AUTORIZADOR = "autorizador"
    SOLO_LECTURA = "solo_lectura"
    CAPTURA_INGRESOS = "captura_ingresos"

class Currency(str, Enum):
    MXN = "MXN"
    USD = "USD"

class AuthorizationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class MovementStatus(str, Enum):
    POSTED = "posted"                    # Contabilizado (aprobado o no requirió autorización)
    PENDING_APPROVAL = "pending_approval" # Pendiente de autorización (no contabiliza)
    REJECTED = "rejected"                 # Rechazado (no contabiliza)

class PartidaGrupo(str, Enum):
    OBRA = "obra"
    GYA = "gya"
    FINANCIEROS = "financieros"
    INGRESOS = "ingresos"

# ========================= MODELS =========================

# Empresa (Multiempresa)
class EmpresaBase(BaseModel):
    nombre: str
    is_active: bool = True

class Empresa(EmpresaBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: UserRole

class UserCreate(UserBase):
    password: str

class User(UserBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    must_change_password: bool = False

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class ForceChangePasswordRequest(BaseModel):
    new_password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User
    must_change_password: bool = False

class ProjectBase(BaseModel):
    code: str
    name: str
    empresa_id: str  # OBLIGATORIO - vincula a empresa
    description: Optional[str] = None
    is_active: bool = True

class Project(ProjectBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Catálogo de Partidas Presupuestales (source of truth)
class CatalogoPartidaBase(BaseModel):
    codigo: str  # 100, 101, 200, etc.
    nombre: str
    grupo: PartidaGrupo
    is_active: bool = True

class CatalogoPartida(CatalogoPartidaBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Legacy Partida - mantener para compatibilidad, pero usar catalogo_partidas
class PartidaBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    is_active: bool = True

class Partida(PartidaBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProviderBase(BaseModel):
    code: str
    name: str
    rfc: Optional[str] = None
    is_active: bool = True

class Provider(ProviderBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BudgetBase(BaseModel):
    project_id: str
    partida_codigo: str  # Código del catálogo (100, 101, etc.)
    year: int
    month: int
    amount_mxn: float
    notes: Optional[str] = None

class Budget(BudgetBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str

class BudgetRequestBase(BudgetBase):
    reason: Optional[str] = None

class BudgetRequest(BudgetRequestBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: AuthorizationStatus = AuthorizationStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    requested_by: str
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

class MovementBase(BaseModel):
    project_id: str
    partida_codigo: str  # Código del catálogo (100, 101, etc.)
    provider_id: str
    date: datetime
    currency: Currency
    amount_original: float
    exchange_rate: float
    amount_mxn: float
    reference: str
    description: Optional[str] = None

class Movement(MovementBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str
    status: MovementStatus = MovementStatus.POSTED
    authorization_id: Optional[str] = None
    reversal_of_id: Optional[str] = None

class MovementCreate(BaseModel):
    project_id: str
    partida_codigo: str  # Código del catálogo
    provider_id: str
    date: str
    currency: Currency
    amount_original: float
    exchange_rate: float
    reference: str
    description: Optional[str] = None

class AuthorizationBase(BaseModel):
    movement_id: Optional[str] = None
    reason: str
    requested_by: str

class Authorization(AuthorizationBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: AuthorizationStatus = AuthorizationStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    notes: Optional[str] = None

class AuthorizationResolve(BaseModel):
    status: AuthorizationStatus
    notes: Optional[str] = None

class AuditLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    user_email: str
    user_role: str
    action: str
    entity: str
    entity_id: str
    changes: Dict[str, Any]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ExchangeRate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str
    rate: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ConfigSetting(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    key: str
    value: Any
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: str

class CSVImportResult(BaseModel):
    total_filas: int
    insertadas: int
    rechazadas: int
    duplicadas_omitidas: int
    errores: List[Dict[str, Any]]
    movements_created: List[str]
    authorizations_required: List[str]

class ExportAuditEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    user_email: str
    action: str  # "IMPORT" or "EXPORT"
    timestamp_inicio: datetime
    timestamp_fin: Optional[datetime] = None
    filtros: Optional[Dict[str, Any]] = None
    conteos: Optional[Dict[str, Any]] = None
    errores_resumen: Optional[List[str]] = None

# ========================= HELPERS =========================
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def validate_password_policy(password: str):
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="La nueva contraseña debe tener al menos 8 caracteres")
    if not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
        raise HTTPException(status_code=422, detail="La nueva contraseña debe contener letras y números")


def create_token(user_id: str, email: str, role: str, must_change_password: bool = False) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "must_change_password": must_change_password,
        "exp": datetime.now(timezone.utc).timestamp() + 86400 * 7
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        if payload.get("must_change_password"):
            allowed_paths = {"/api/auth/force-change-password", "/api/auth/logout", "/api/auth/me", "/api/auth/permissions"}
            if request.url.path not in allowed_paths:
                raise HTTPException(status_code=403, detail="Debes cambiar tu contraseña para continuar")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

def require_roles(*roles: UserRole):
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in [r.value for r in roles]:
            raise HTTPException(status_code=403, detail="Permisos insuficientes para esta acción")
        return current_user
    return role_checker

# ========================= RBAC PERMISSIONS MATRIX =========================
# Define granular permissions per action type
class Permission(str, Enum):
    # Dashboard/Reports
    VIEW_DASHBOARD = "view_dashboard"
    VIEW_REPORTS = "view_reports"
    EXPORT_DATA = "export_data"
    
    # Movements
    CREATE_MOVEMENT = "create_movement"
    VIEW_MOVEMENTS = "view_movements"
    IMPORT_MOVEMENTS = "import_movements"
    
    # Authorizations
    VIEW_AUTHORIZATIONS = "view_authorizations"
    APPROVE_REJECT = "approve_reject"
    
    # Catalogs (empresas, proyectos, partidas, proveedores)
    VIEW_CATALOGS = "view_catalogs"
    MANAGE_CATALOGS = "manage_catalogs"
    
    # Budgets
    VIEW_BUDGETS = "view_budgets"
    MANAGE_BUDGETS = "manage_budgets"
    REQUEST_BUDGETS = "request_budgets"
    
    # Users
    VIEW_USERS = "view_users"
    MANAGE_USERS = "manage_users"
    
    # Audit
    VIEW_AUDIT = "view_audit"
    EXPORT_AUDIT = "export_audit"

# Role -> Permissions mapping
ROLE_PERMISSIONS = {
    UserRole.ADMIN.value: [p.value for p in Permission],  # Admin: ALL
    
    UserRole.FINANZAS.value: [
        Permission.VIEW_DASHBOARD.value,
        Permission.VIEW_REPORTS.value,
        Permission.EXPORT_DATA.value,
        Permission.CREATE_MOVEMENT.value,
        Permission.VIEW_MOVEMENTS.value,
        Permission.IMPORT_MOVEMENTS.value,
        Permission.VIEW_AUTHORIZATIONS.value,
        Permission.VIEW_CATALOGS.value,
        Permission.VIEW_BUDGETS.value,
        Permission.REQUEST_BUDGETS.value,
        Permission.MANAGE_CATALOGS.value,
    ],
    
    UserRole.AUTORIZADOR.value: [
        Permission.VIEW_DASHBOARD.value,
        Permission.VIEW_REPORTS.value,
        Permission.EXPORT_DATA.value,
        Permission.VIEW_MOVEMENTS.value,
        Permission.VIEW_AUTHORIZATIONS.value,
        Permission.APPROVE_REJECT.value,
        Permission.VIEW_CATALOGS.value,
        Permission.VIEW_BUDGETS.value,
        Permission.VIEW_AUDIT.value,
    ],
    
    UserRole.CAPTURA_INGRESOS.value: [
        Permission.VIEW_DASHBOARD.value,
        Permission.VIEW_REPORTS.value,
        Permission.CREATE_MOVEMENT.value,
        Permission.VIEW_MOVEMENTS.value,
        Permission.VIEW_CATALOGS.value,
        Permission.VIEW_BUDGETS.value,
    ],

    UserRole.SOLO_LECTURA.value: [
        Permission.VIEW_DASHBOARD.value,
        Permission.VIEW_REPORTS.value,
        Permission.VIEW_MOVEMENTS.value,
        Permission.VIEW_AUTHORIZATIONS.value,
        Permission.VIEW_CATALOGS.value,
        Permission.VIEW_BUDGETS.value,
    ],
}

def require_permission(*permissions: Permission):
    """Check if user has at least one of the required permissions"""
    async def permission_checker(current_user: dict = Depends(get_current_user)):
        user_role = current_user.get("role")
        user_permissions = ROLE_PERMISSIONS.get(user_role, [])
        
        if not any(p.value in user_permissions for p in permissions):
            raise HTTPException(
                status_code=403, 
                detail=f"Permisos insuficientes. Se requiere: {', '.join([p.value for p in permissions])}"
            )
        return current_user
    return permission_checker

async def log_audit(user: dict, action: str, entity_type: str, entity_id: str, changes: dict, ip_address: str = None):
    """Enhanced audit logging with IP and standardized format"""
    audit = {
        "id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "user_email": user["email"],
        "user_role": user["role"],
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "changes": changes,
        "ip_address": ip_address,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await db.audit_logs.insert_one(audit)

async def log_admin_action(
    request: Request,
    user: dict,
    action: str,
    entity: str,
    entity_id: str,
    success: bool,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    message: Optional[str] = None,
):
    payload = {
        "result": "success" if success else "failure",
        "before": before,
        "after": after,
        "message": message,
        "user_agent": request.headers.get("user-agent"),
    }
    await log_audit(user, action, entity, entity_id, payload, ip_address=request.client.host if request.client else None)


def ensure_admin(current_user: dict) -> dict:
    if current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Solo administradores")
    return current_user


def active_query(include_inactive: bool = False, extra: Optional[dict] = None) -> dict:
    query = extra.copy() if extra else {}
    if not include_inactive:
        query["is_active"] = {"$ne": False}
    return query


async def assert_no_references(entity: str, entity_id: str):
    checks = {
        "empresas": [("projects", {"empresa_id": entity_id}, "proyectos")],
        "projects": [
            ("budgets", {"project_id": entity_id}, "presupuestos"),
            ("movements", {"project_id": entity_id}, "movimientos"),
        ],
        "providers": [("movements", {"provider_id": entity_id}, "movimientos")],
        "users": [
            ("movements", {"created_by": entity_id}, "movimientos"),
            ("budgets", {"created_by": entity_id}, "presupuestos"),
            ("authorizations", {"requested_by": entity_id}, "autorizaciones"),
        ],
    }
    for collection, query, label in checks.get(entity, []):
        if await db[collection].find_one(query, {"_id": 0}):
            raise HTTPException(status_code=409, detail=f"No se puede eliminar físicamente: tiene referencias en {label}")

def get_traffic_light(percentage: float) -> str:
    if percentage <= 90:
        return "green"
    elif percentage <= 100:
        return "yellow"
    else:
        return "red"

def parse_date_tijuana(date_str: str) -> datetime:
    parsed = date_parser.parse(date_str)
    if parsed.tzinfo is None:
        parsed = TIMEZONE.localize(parsed)
    return parsed.astimezone(pytz.UTC)

def to_tijuana(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    return dt.astimezone(TIMEZONE)

def get_year_range() -> tuple[int, int]:
    current_year = to_tijuana(datetime.now(timezone.utc)).year
    from_year = min(2025, current_year)
    to_year = max(current_year + 10, 2031)
    return from_year, to_year

def validate_year_in_range(year: int):
    from_year, to_year = get_year_range()
    if year < from_year or year > to_year:
        raise HTTPException(status_code=422, detail=f"Año fuera de rango permitido ({from_year}-{to_year})")

def validate_date_in_range(dt: datetime):
    validate_year_in_range(to_tijuana(dt).year)

def is_ingresos_partida(codigo: str) -> bool:
    return str(codigo).startswith("4")

# ========================= AUTH ROUTES =========================
@api_router.post("/auth/register", response_model=User)
async def register(user_data: UserCreate, current_user: dict = Depends(require_permission(Permission.MANAGE_USERS))):
    existing = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    
    user = User(**user_data.model_dump(exclude={"password"}))
    doc = user.model_dump()
    doc['password_hash'] = hash_password(user_data.password)
    doc['must_change_password'] = False
    doc['created_at'] = doc['created_at'].isoformat()
    await db.users.insert_one(doc)
    return user

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user_doc = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user_doc:
        logger.info("Login failed: user not found for email=%s", credentials.email)
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if not verify_password(credentials.password, user_doc.get('password_hash', '')):
        logger.info("Login failed: invalid password for email=%s", credentials.email)
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if not user_doc.get('is_active', True):
        logger.info("Login failed: inactive user id=%s", user_doc.get('id'))
        raise HTTPException(status_code=401, detail="Usuario desactivado")
    
    must_change_password = bool(user_doc.get('must_change_password', False))
    token = create_token(user_doc['id'], user_doc['email'], user_doc['role'], must_change_password=must_change_password)
    user = User(**{k: v for k, v in user_doc.items() if k != 'password_hash'})
    
    # Log successful login
    await log_audit(
        {"user_id": user_doc['id'], "email": user_doc['email'], "role": user_doc['role']},
        "LOGIN",
        "auth",
        user_doc['id'],
        {"status": "success"}
    )
    
    return TokenResponse(access_token=token, user=user, must_change_password=must_change_password)

@api_router.post("/auth/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Log user logout"""
    await log_audit(current_user, "LOGOUT", "auth", current_user["user_id"], {"status": "success"})
    return {"message": "Sesión cerrada"}

@api_router.post("/auth/change-password")
async def change_password(payload: ChangePasswordRequest, request: Request, current_user: dict = Depends(get_current_user)):
    user_doc = await db.users.find_one({"id": current_user["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not verify_password(payload.current_password, user_doc.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="La contraseña actual es incorrecta")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=422, detail="La nueva contraseña debe ser diferente a la actual")
    validate_password_policy(payload.new_password)

    await db.users.update_one({"id": user_doc["id"]}, {"$set": {
        "password_hash": hash_password(payload.new_password),
        "must_change_password": False,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }})
    await log_audit(current_user, "PASSWORD_CHANGED", "users", user_doc["id"], {"source": "settings"}, ip_address=request.client.host if request.client else None)
    fresh = await db.users.find_one({"id": user_doc["id"]}, {"_id": 0})
    token = create_token(fresh["id"], fresh["email"], fresh["role"], must_change_password=False)
    user = User(**{k: v for k, v in fresh.items() if k != "password_hash"})
    return TokenResponse(access_token=token, user=user, must_change_password=False)


@api_router.post("/auth/force-change-password")
async def force_change_password(payload: ForceChangePasswordRequest, request: Request, current_user: dict = Depends(get_current_user)):
    user_doc = await db.users.find_one({"id": current_user["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not user_doc.get("must_change_password", False):
        raise HTTPException(status_code=403, detail="El usuario no requiere cambio forzado de contraseña")
    validate_password_policy(payload.new_password)
    if verify_password(payload.new_password, user_doc.get("password_hash", "")):
        raise HTTPException(status_code=422, detail="La nueva contraseña debe ser diferente a la actual")

    await db.users.update_one({"id": user_doc["id"]}, {"$set": {
        "password_hash": hash_password(payload.new_password),
        "must_change_password": False,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }})
    await log_audit(current_user, "PASSWORD_CHANGED", "users", user_doc["id"], {"source": "force_change"}, ip_address=request.client.host if request.client else None)
    fresh = await db.users.find_one({"id": user_doc["id"]}, {"_id": 0})
    token = create_token(fresh["id"], fresh["email"], fresh["role"], must_change_password=False)
    user = User(**{k: v for k, v in fresh.items() if k != "password_hash"})
    return TokenResponse(access_token=token, user=user, must_change_password=False)

@api_router.get("/auth/me", response_model=User)
async def get_me(current_user: dict = Depends(get_current_user)):
    user_doc = await db.users.find_one({"id": current_user["user_id"]}, {"_id": 0, "password_hash": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return User(**user_doc)

@api_router.get("/auth/permissions")
async def get_my_permissions(current_user: dict = Depends(get_current_user)):
    """Return current user's permissions for frontend RBAC"""
    role = current_user.get("role")
    permissions = ROLE_PERMISSIONS.get(role, [])
    return {
        "role": role,
        "permissions": permissions
    }

# ========================= USER ROUTES =========================
@api_router.get("/users", response_model=List[User])
async def get_users(current_user: dict = Depends(require_permission(Permission.VIEW_USERS, Permission.MANAGE_USERS))):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return [User(**u) for u in users]

@api_router.put("/users/{user_id}")
async def update_user(user_id: str, updates: dict, current_user: dict = Depends(require_permission(Permission.MANAGE_USERS))):
    old_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not old_doc:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    allowed_fields = ["name", "role", "is_active"]
    update_data = {k: v for k, v in updates.items() if k in allowed_fields}
    
    await db.users.update_one({"id": user_id}, {"$set": update_data})
    await log_audit(current_user, "UPDATE", "users", user_id, {
        "before": {k: old_doc.get(k) for k in allowed_fields},
        "after": update_data
    })
    return {"message": "Usuario actualizado"}

# ========================= EMPRESA ROUTES =========================
@api_router.get("/empresas")
async def get_empresas(current_user: dict = Depends(require_permission(Permission.VIEW_CATALOGS))):
    empresas = await db.empresas.find({}, {"_id": 0}).to_list(1000)
    return empresas

@api_router.post("/empresas")
async def create_empresa(empresa_data: EmpresaBase, current_user: dict = Depends(require_permission(Permission.MANAGE_CATALOGS))):
    existing = await db.empresas.find_one({"nombre": empresa_data.nombre}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Empresa ya existe")
    
    empresa = Empresa(**empresa_data.model_dump())
    doc = empresa.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['updated_at'] = doc['updated_at'].isoformat()
    await db.empresas.insert_one(doc)
    await log_audit(current_user, "CREATE", "empresas", empresa.id, {"data": {"nombre": doc['nombre']}})
    doc.pop('_id', None)
    return doc

# ========================= CATALOGO PARTIDAS ROUTES =========================
@api_router.get("/catalogo-partidas")
async def get_catalogo_partidas(current_user: dict = Depends(require_permission(Permission.VIEW_CATALOGS))):
    partidas = await db.catalogo_partidas.find({}, {"_id": 0}).sort("codigo", 1).to_list(1000)
    return partidas

@api_router.get("/catalogo-partidas/{codigo}")
async def get_catalogo_partida(codigo: str, current_user: dict = Depends(require_permission(Permission.VIEW_CATALOGS))):
    partida = await db.catalogo_partidas.find_one({"codigo": codigo}, {"_id": 0})
    if not partida:
        raise HTTPException(status_code=404, detail=f"Partida {codigo} no encontrada en catálogo")
    return partida

# Helper: validar partida existe y está activa
async def validate_partida(codigo: str) -> dict:
    partida = await db.catalogo_partidas.find_one({"codigo": codigo}, {"_id": 0})
    if not partida:
        raise HTTPException(status_code=400, detail=f"Partida '{codigo}' no existe en el catálogo")
    if not partida.get('is_active', True):
        raise HTTPException(status_code=400, detail=f"Partida '{codigo}' está inactiva")
    return partida

# ========================= PROJECT ROUTES =========================
@api_router.get("/projects")
async def get_projects(
    empresa_id: Optional[str] = None,
    current_user: dict = Depends(require_permission(Permission.VIEW_CATALOGS))
):
    query = {}
    if empresa_id:
        query["empresa_id"] = empresa_id
    projects = await db.projects.find(query, {"_id": 0}).to_list(1000)
    return projects

@api_router.post("/projects")
async def create_project(project_data: ProjectBase, current_user: dict = Depends(require_permission(Permission.MANAGE_CATALOGS))):
    # Validar que empresa existe
    empresa = await db.empresas.find_one({"id": project_data.empresa_id}, {"_id": 0})
    if not empresa:
        raise HTTPException(status_code=400, detail="Empresa no encontrada")
    
    project = Project(**project_data.model_dump())
    doc = project.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.projects.insert_one(doc)
    await log_audit(current_user, "CREATE", "projects", project.id, {"data": {"code": doc['code'], "name": doc['name'], "empresa_id": doc['empresa_id']}})
    doc.pop('_id', None)
    return doc

@api_router.put("/projects/{project_id}")
async def update_project(project_id: str, updates: ProjectBase, current_user: dict = Depends(require_permission(Permission.MANAGE_CATALOGS))):
    old_doc = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not old_doc:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    
    # Validar empresa si se cambia
    if updates.empresa_id:
        empresa = await db.empresas.find_one({"id": updates.empresa_id}, {"_id": 0})
        if not empresa:
            raise HTTPException(status_code=400, detail="Empresa no encontrada")
    
    update_data = updates.model_dump()
    await db.projects.update_one({"id": project_id}, {"$set": update_data})
    await log_audit(current_user, "UPDATE", "projects", project_id, {
        "before": {"code": old_doc.get('code'), "name": old_doc.get('name')},
        "after": {"code": update_data.get('code'), "name": update_data.get('name')}
    })
    
    updated = await db.projects.find_one({"id": project_id}, {"_id": 0})
    return Project(**updated)

# ========================= PARTIDA ROUTES =========================
@api_router.get("/partidas", response_model=List[Partida])
async def get_partidas(current_user: dict = Depends(require_permission(Permission.VIEW_CATALOGS))):
    partidas = await db.partidas.find({}, {"_id": 0}).to_list(1000)
    return [Partida(**p) for p in partidas]

@api_router.post("/partidas", response_model=Partida)
async def create_partida(partida_data: PartidaBase, current_user: dict = Depends(require_permission(Permission.MANAGE_CATALOGS))):
    partida = Partida(**partida_data.model_dump())
    doc = partida.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.partidas.insert_one(doc)
    await log_audit(current_user, "CREATE", "partidas", partida.id, {"data": {"code": doc['code'], "name": doc['name']}})
    return partida

@api_router.put("/partidas/{partida_id}", response_model=Partida)
async def update_partida(partida_id: str, updates: PartidaBase, current_user: dict = Depends(require_permission(Permission.MANAGE_CATALOGS))):
    old_doc = await db.partidas.find_one({"id": partida_id}, {"_id": 0})
    if not old_doc:
        raise HTTPException(status_code=404, detail="Partida no encontrada")
    
    update_data = updates.model_dump()
    await db.partidas.update_one({"id": partida_id}, {"$set": update_data})
    await log_audit(current_user, "UPDATE", "partidas", partida_id, {
        "before": {"code": old_doc.get('code'), "name": old_doc.get('name')},
        "after": {"code": update_data.get('code'), "name": update_data.get('name')}
    })
    
    updated = await db.partidas.find_one({"id": partida_id}, {"_id": 0})
    return Partida(**updated)

# ========================= PROVIDER ROUTES =========================
@api_router.get("/providers", response_model=List[Provider])
async def get_providers(include_inactive: bool = False, current_user: dict = Depends(require_permission(Permission.VIEW_CATALOGS))):
    query = {} if include_inactive else {"is_active": {"$ne": False}}
    providers = await db.providers.find(query, {"_id": 0}).to_list(1000)
    return [Provider(**p) for p in providers]

@api_router.post("/providers", response_model=Provider)
async def create_provider(provider_data: ProviderBase, current_user: dict = Depends(require_permission(Permission.MANAGE_CATALOGS))):
    existing = await db.providers.find_one({"code": provider_data.code}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Proveedor con este código ya existe")
    provider = Provider(**provider_data.model_dump())
    doc = provider.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.providers.insert_one(doc)
    await log_audit(current_user, "CREATE", "providers", provider.id, {"data": {"code": doc['code'], "name": doc['name']}})
    return provider

@api_router.put("/providers/{provider_id}", response_model=Provider)
async def update_provider(provider_id: str, updates: ProviderBase, current_user: dict = Depends(require_permission(Permission.MANAGE_CATALOGS))):
    old_doc = await db.providers.find_one({"id": provider_id}, {"_id": 0})
    if not old_doc:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    
    update_data = updates.model_dump()
    await db.providers.update_one({"id": provider_id}, {"$set": update_data})
    await log_audit(current_user, "UPDATE", "providers", provider_id, {
        "before": {"code": old_doc.get('code'), "name": old_doc.get('name')},
        "after": {"code": update_data.get('code'), "name": update_data.get('name')}
    })
    
    updated = await db.providers.find_one({"id": provider_id}, {"_id": 0})
    return Provider(**updated)


@api_router.put("/providers/{provider_id}/toggle")
async def toggle_provider(provider_id: str, current_user: dict = Depends(require_permission(Permission.MANAGE_CATALOGS))):
    provider = await db.providers.find_one({"id": provider_id}, {"_id": 0})
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    new_status = not provider.get("is_active", True)
    await db.providers.update_one({"id": provider_id}, {"$set": {"is_active": new_status}})
    await log_audit(current_user, "TOGGLE", "providers", provider_id, {"is_active": new_status})
    updated = await db.providers.find_one({"id": provider_id}, {"_id": 0})
    return Provider(**updated)

@api_router.get("/providers/export")
async def export_providers(format: str = Query("csv", pattern="^(csv|xlsx)$"), current_user: dict = Depends(require_permission(Permission.VIEW_CATALOGS))):
    providers = await db.providers.find({}, {"_id": 0}).sort("code", 1).to_list(5000)
    await log_audit(current_user, "EXPORT", "providers", "batch", {"format": format, "count": len(providers)})
    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["code", "name", "rfc", "is_active"])
        writer.writeheader()
        for p in providers:
            writer.writerow({k: p.get(k) for k in ["code", "name", "rfc", "is_active"]})
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=providers.csv"})
    wb = Workbook()
    ws = wb.active
    ws.title = "providers"
    ws.append(["code", "name", "rfc", "is_active"])
    for p in providers:
        ws.append([p.get("code"), p.get("name"), p.get("rfc"), p.get("is_active", True)])
    b=io.BytesIO(); wb.save(b); b.seek(0)
    return StreamingResponse(b, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=providers.xlsx"})

@api_router.post("/providers/import")
async def import_providers(file: UploadFile = File(...), current_user: dict = Depends(require_permission(Permission.MANAGE_CATALOGS))):
    filename=(file.filename or "").lower()
    content=await file.read()
    rows=[]
    if filename.endswith(".csv"):
        text=content.decode("utf-8-sig")
        rows=list(csv.DictReader(io.StringIO(text)))
    elif filename.endswith(".xlsx"):
        wb=load_workbook(io.BytesIO(content), read_only=True)
        ws=wb.active
        headers=[str(c.value).strip() if c.value is not None else "" for c in next(ws.rows)]
        for r in ws.iter_rows(min_row=2, values_only=True):
            rows.append({headers[i]: ("" if v is None else str(v)) for i,v in enumerate(r)})
    else:
        raise HTTPException(status_code=400, detail="Formato soportado: csv/xlsx")
    required=["code","name"]
    errors=[]; duplicates=[]; created=0; updated=0
    seen=set()
    for idx,row in enumerate(rows, start=2):
        missing=[c for c in required if not str(row.get(c,"")).strip()]
        if missing:
            errors.append({"row": idx, "error": f"Columnas requeridas faltantes: {', '.join(missing)}"}); continue
        code=str(row.get("code")).strip().upper(); name=str(row.get("name")).strip(); rfc=str(row.get("rfc","")).strip().upper() or None
        is_active=str(row.get("is_active","true")).strip().lower() not in {"false","0","no","inactive"}
        if code in seen:
            duplicates.append({"row": idx, "code": code}); continue
        seen.add(code)
        existing=await db.providers.find_one({"code": code},{"_id":0})
        payload={"code":code,"name":name,"rfc":rfc,"is_active":is_active}
        if existing:
            await db.providers.update_one({"id":existing["id"]},{"$set":payload}); updated += 1
        else:
            provider=Provider(**payload); doc=provider.model_dump(); doc["created_at"]=doc["created_at"].isoformat(); await db.providers.insert_one(doc); created += 1
    await log_audit(current_user, "IMPORT", "providers", "batch", {"filename": file.filename, "rows": len(rows), "created": created, "updated": updated, "duplicates": len(duplicates), "errors": len(errors)})
    return {"total": len(rows), "created": created, "updated": updated, "duplicates": duplicates, "errors": errors}

# ========================= BUDGET ROUTES =========================
@api_router.get("/budgets")
async def get_budgets(
    project_id: Optional[str] = None,
    partida_codigo: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    current_user: dict = Depends(require_permission(Permission.VIEW_BUDGETS))
):
    query = {}
    if project_id:
        query["project_id"] = project_id
    if partida_codigo:
        query["partida_codigo"] = partida_codigo
    if year:
        query["year"] = year
    if month:
        query["month"] = month
    
    budgets = await db.budgets.find(query, {"_id": 0}).to_list(1000)
    return budgets

@api_router.post("/budgets")
async def create_budget(budget_data: BudgetBase, current_user: dict = Depends(require_permission(Permission.MANAGE_BUDGETS))):
    validate_year_in_range(budget_data.year)
    if current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Solo admin puede crear presupuestos directamente")
    # VALIDACIÓN BLOQUEANTE: partida debe existir en catálogo
    await validate_partida(budget_data.partida_codigo)
    
    # Validar proyecto existe
    project = await db.projects.find_one({"id": budget_data.project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=400, detail="Proyecto no encontrado")
    
    existing = await db.budgets.find_one({
        "project_id": budget_data.project_id,
        "partida_codigo": budget_data.partida_codigo,
        "year": budget_data.year,
        "month": budget_data.month
    }, {"_id": 0})
    
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe presupuesto para este proyecto/partida/mes")
    
    budget = Budget(**budget_data.model_dump(), created_by=current_user["user_id"])
    doc = budget.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.budgets.insert_one(doc)
    await log_audit(current_user, "CREATE", "budgets", budget.id, {
        "data": {
            "project_id": doc['project_id'],
            "partida_codigo": doc['partida_codigo'],
            "year": doc['year'],
            "month": doc['month'],
            "amount_mxn": doc['amount_mxn']
        }
    })
    doc.pop('_id', None)
    return doc

@api_router.put("/budgets/{budget_id}")
async def update_budget(budget_id: str, updates: BudgetBase, current_user: dict = Depends(require_permission(Permission.MANAGE_BUDGETS))):
    validate_year_in_range(updates.year)
    # VALIDACIÓN BLOQUEANTE: partida debe existir
    await validate_partida(updates.partida_codigo)
    
    old_doc = await db.budgets.find_one({"id": budget_id}, {"_id": 0})
    if not old_doc:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    
    update_data = updates.model_dump()
    await db.budgets.update_one({"id": budget_id}, {"$set": update_data})
    await log_audit(current_user, "UPDATE", "budgets", budget_id, {
        "before": {"amount_mxn": old_doc.get('amount_mxn')},
        "after": {"amount_mxn": update_data.get('amount_mxn')}
    })
    
    updated = await db.budgets.find_one({"id": budget_id}, {"_id": 0})
    return updated

@api_router.delete("/budgets/{budget_id}")
async def delete_budget(budget_id: str, current_user: dict = Depends(require_permission(Permission.MANAGE_BUDGETS))):
    old_doc = await db.budgets.find_one({"id": budget_id}, {"_id": 0})
    if not old_doc:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    
    await db.budgets.delete_one({"id": budget_id})
    await log_audit(current_user, "DELETE", "budgets", budget_id, {
        "deleted": {
            "project_id": old_doc.get('project_id'),
            "partida_codigo": old_doc.get('partida_codigo'),
            "amount_mxn": old_doc.get('amount_mxn')
        }
    })
    return {"message": "Presupuesto eliminado"}

@api_router.get("/budget-requests")
async def get_budget_requests(status: Optional[str] = None, current_user: dict = Depends(require_permission(Permission.VIEW_BUDGETS))):
    query = {}
    if status:
        query["status"] = status
    if current_user.get("role") == UserRole.FINANZAS.value:
        query["requested_by"] = current_user["user_id"]
    return await db.budget_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)

@api_router.post("/budget-requests")
async def create_budget_request(payload: BudgetRequestBase, current_user: dict = Depends(require_permission(Permission.REQUEST_BUDGETS, Permission.MANAGE_BUDGETS))):
    validate_year_in_range(payload.year)
    await validate_partida(payload.partida_codigo)
    if current_user.get("role") not in [UserRole.FINANZAS.value, UserRole.ADMIN.value]:
        raise HTTPException(status_code=403, detail="Rol sin permisos para solicitar presupuesto")
    req = BudgetRequest(**payload.model_dump(), requested_by=current_user["user_id"])
    doc = req.model_dump(); doc["created_at"] = doc["created_at"].isoformat()
    await db.budget_requests.insert_one(doc)
    await log_audit(current_user, "CREATE", "budget_requests", req.id, {"data": payload.model_dump()})
    return doc

@api_router.put("/budget-requests/{request_id}/resolve")
async def resolve_budget_request(request_id: str, resolution: AuthorizationResolve, current_user: dict = Depends(require_permission(Permission.MANAGE_BUDGETS))):
    if current_user.get("role") != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Solo admin puede resolver solicitudes")
    req = await db.budget_requests.find_one({"id": request_id}, {"_id": 0})
    if not req:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if req.get("status") != AuthorizationStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Solicitud ya resuelta")
    update = {"status": resolution.status.value, "resolved_at": datetime.now(timezone.utc).isoformat(), "resolved_by": current_user["user_id"]}
    await db.budget_requests.update_one({"id": request_id}, {"$set": update})
    if resolution.status == AuthorizationStatus.APPROVED:
        existing = await db.budgets.find_one({"project_id": req["project_id"], "partida_codigo": req["partida_codigo"], "year": req["year"], "month": req["month"]}, {"_id":0})
        if not existing:
            budget = Budget(project_id=req["project_id"], partida_codigo=req["partida_codigo"], year=req["year"], month=req["month"], amount_mxn=req["amount_mxn"], notes=req.get("notes"), created_by=current_user["user_id"])
            d=budget.model_dump(); d["created_at"]=d["created_at"].isoformat(); await db.budgets.insert_one(d)
    await log_audit(current_user, f"BUDGET_REQUEST_{resolution.status.value.upper()}", "budget_requests", request_id, {"notes": resolution.notes})
    return {"message": f"Solicitud {resolution.status.value}"}

# ========================= EXCHANGE RATE ROUTES =========================
@api_router.get("/exchange-rates")
async def get_exchange_rates(current_user: dict = Depends(require_permission(Permission.VIEW_CATALOGS))):
    rates = await db.exchange_rates.find({}, {"_id": 0}).to_list(1000)
    return rates

@api_router.post("/exchange-rates")
async def create_exchange_rate(date_str: str, rate: float, current_user: dict = Depends(require_permission(Permission.MANAGE_CATALOGS))):
    existing = await db.exchange_rates.find_one({"date": date_str}, {"_id": 0})
    if existing:
        await db.exchange_rates.update_one({"date": date_str}, {"$set": {"rate": rate}})
        await log_audit(current_user, "UPDATE", "exchange_rates", date_str, {"rate": rate})
        return {"message": "Tipo de cambio actualizado"}
    
    exchange = ExchangeRate(date=date_str, rate=rate)
    doc = exchange.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.exchange_rates.insert_one(doc)
    await log_audit(current_user, "CREATE", "exchange_rates", date_str, {"rate": rate})
    return {"message": "Tipo de cambio creado"}

# ========================= MOVEMENT ROUTES =========================
@api_router.get("/movements")
async def get_movements(
    project_id: Optional[str] = None,
    partida_codigo: Optional[str] = None,
    provider_id: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(require_permission(Permission.VIEW_MOVEMENTS))
):
    query = {}
    if project_id:
        query["project_id"] = project_id
    if partida_codigo:
        query["partida_codigo"] = partida_codigo
    if provider_id:
        query["provider_id"] = provider_id
    if status:
        query["status"] = status
    
    movements = await db.movements.find(query, {"_id": 0}).to_list(5000)
    if year:
        validate_year_in_range(year)
    if year or month:
        filtered = []
        for m in movements:
            mov_date = date_parser.parse(m['date']) if isinstance(m['date'], str) else m['date']
            if year and mov_date.year != year:
                continue
            if month and mov_date.month != month:
                continue
            filtered.append(m)
        movements = filtered
    
    return movements

@api_router.post("/movements")
async def create_movement(movement_data: MovementCreate, current_user: dict = Depends(require_permission(Permission.CREATE_MOVEMENT))):
    # VALIDACIÓN BLOQUEANTE: partida debe existir en catálogo
    await validate_partida(movement_data.partida_codigo)
    
    # Validate references
    project = await db.projects.find_one({"id": movement_data.project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=400, detail="Proyecto no válido")
    
    provider = await db.providers.find_one({"id": movement_data.provider_id}, {"_id": 0})
    if not provider:
        raise HTTPException(status_code=400, detail="Proveedor no válido")
    
    if movement_data.amount_original <= 0:
        raise HTTPException(status_code=400, detail="Monto debe ser mayor a 0")
    
    # Parse date
    parsed_date = parse_date_tijuana(movement_data.date)
    validate_date_in_range(parsed_date)
    if current_user.get("role") == UserRole.CAPTURA_INGRESOS.value and not is_ingresos_partida(movement_data.partida_codigo):
        raise HTTPException(status_code=403, detail="captura_ingresos solo puede registrar partidas 4xx")
    amount_mxn = movement_data.amount_original * movement_data.exchange_rate
    
    # Check for duplicates
    dup_check = await db.movements.find_one({
        "date": parsed_date.isoformat(),
        "provider_id": movement_data.provider_id,
        "amount_original": movement_data.amount_original,
        "reference": movement_data.reference
    }, {"_id": 0})
    
    if dup_check:
        raise HTTPException(status_code=400, detail="Movimiento duplicado detectado")
    
    # Check budget status
    year = parsed_date.year
    month = parsed_date.month
    
    budget = await db.budgets.find_one({
        "project_id": movement_data.project_id,
        "partida_codigo": movement_data.partida_codigo,
        "year": year,
        "month": month
    }, {"_id": 0})
    
    # Calculate current spent - SOLO movimientos posted
    current_movements = await db.movements.find({
        "project_id": movement_data.project_id,
        "partida_codigo": movement_data.partida_codigo,
        "status": MovementStatus.POSTED.value
    }, {"_id": 0}).to_list(5000)
    
    current_spent = sum(
        m['amount_mxn'] for m in current_movements
        if date_parser.parse(m['date']).year == year and date_parser.parse(m['date']).month == month
    )
    
    budget_amount = budget['amount_mxn'] if budget else 0
    new_total = current_spent + amount_mxn
    
    # Determine if authorization required: >100% OR presupuesto $0
    requires_auth = False
    auth_reason = ""
    percentage_if_posted = (new_total / budget_amount * 100) if budget_amount > 0 else 0
    
    if budget_amount == 0:
        requires_auth = True
        auth_reason = "Presupuesto no definido ($0) - requiere autorización"
    elif percentage_if_posted > 100:
        requires_auth = True
        auth_reason = f"Exceso de presupuesto: {percentage_if_posted:.1f}% (>100%)"
    
    movement = Movement(
        project_id=movement_data.project_id,
        partida_codigo=movement_data.partida_codigo,
        provider_id=movement_data.provider_id,
        date=parsed_date,
        currency=movement_data.currency,
        amount_original=movement_data.amount_original,
        exchange_rate=movement_data.exchange_rate,
        amount_mxn=amount_mxn,
        reference=movement_data.reference,
        description=movement_data.description,
        created_by=current_user["user_id"],
        status=MovementStatus.PENDING_APPROVAL if requires_auth else MovementStatus.POSTED
    )
    
    doc = movement.model_dump()
    doc['date'] = doc['date'].isoformat()
    doc['created_at'] = doc['created_at'].isoformat()
    
    # Create authorization record if needed
    if requires_auth:
        auth = Authorization(
            movement_id=movement.id,
            reason=auth_reason,
            requested_by=current_user["user_id"]
        )
        auth_doc = auth.model_dump()
        auth_doc['created_at'] = auth_doc['created_at'].isoformat()
        # Add budget context for UI display
        auth_doc['budget_context'] = {
            'partida_codigo': movement_data.partida_codigo,
            'presupuesto': budget_amount,
            'ejecutado_actual': current_spent,
            'monto_movimiento': amount_mxn,
            'porcentaje_actual': (current_spent / budget_amount * 100) if budget_amount > 0 else 0,
            'porcentaje_si_aprueba': percentage_if_posted
        }
        await db.authorizations.insert_one(auth_doc)
        doc['authorization_id'] = auth.id
    
    await db.movements.insert_one(doc)
    
    # Remove MongoDB _id before returning
    doc.pop('_id', None)
    
    await log_audit(current_user, "CREATE", "movements", movement.id, {"data": doc, "requires_auth": requires_auth})
    
    return {"movement": doc, "requires_authorization": requires_auth, "reason": auth_reason if requires_auth else None}

@api_router.post("/movements/import-csv")
async def import_movements_csv(file: UploadFile = File(...), current_user: dict = Depends(require_permission(Permission.IMPORT_MOVEMENTS))):
    """
    Import CSV con validaciones estrictas según especificación Entrega B.
    Columnas requeridas: fecha, empresa, proyecto, partida, proveedor, moneda, monto, tipo_cambio, referencia, descripcion
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos CSV")
    
    # Log inicio de import
    import_start = datetime.now(timezone.utc)
    
    content = await file.read()
    # Try different encodings
    try:
        decoded = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        try:
            decoded = content.decode('latin-1')
        except UnicodeDecodeError:
            decoded = content.decode('utf-8', errors='replace')
    
    reader = csv.DictReader(io.StringIO(decoded))
    
    results = CSVImportResult(
        total_filas=0,
        insertadas=0,
        rechazadas=0,
        duplicadas_omitidas=0,
        errores=[],
        movements_created=[],
        authorizations_required=[]
    )
    
    # Columnas requeridas exactas
    required_columns = ['fecha', 'empresa', 'proyecto', 'partida', 'proveedor', 'moneda', 'monto', 'referencia']
    
    # Get lookups - empresas, proyectos, partidas del catálogo, proveedores
    empresas = {e['nombre'].upper(): e for e in await db.empresas.find({}, {"_id": 0}).to_list(1000)}
    empresas_by_id = {e['id']: e for e in await db.empresas.find({}, {"_id": 0}).to_list(1000)}
    
    projects_list = await db.projects.find({}, {"_id": 0}).to_list(1000)
    # Map by code AND name (upper) for flexibility
    projects_by_code = {p['code'].upper(): p for p in projects_list}
    projects_by_name = {p['name'].upper(): p for p in projects_list}
    
    # Catálogo de partidas (source of truth)
    catalogo = await db.catalogo_partidas.find({}, {"_id": 0}).to_list(1000)
    partidas_by_codigo = {p['codigo']: p for p in catalogo}
    partidas_by_nombre = {p['nombre'].upper(): p for p in catalogo}
    
    providers_list = await db.providers.find({}, {"_id": 0}).to_list(1000)
    providers_by_code = {p['code'].upper(): p for p in providers_list}
    providers_by_name = {p['name'].upper(): p for p in providers_list}
    
    row_num = 1
    rows_processed = []
    
    for row in reader:
        row_num += 1
        results.total_filas += 1
        errors = []
        
        # Normalize column names (lowercase, strip)
        row = {k.lower().strip(): v.strip() if v else '' for k, v in row.items()}
        
        # Validate required columns exist
        for col in required_columns:
            if col not in row or not row.get(col, '').strip():
                errors.append({"columna": col, "motivo": f"Campo '{col}' requerido y vacío"})
        
        if errors:
            results.errores.append({"fila": row_num, "errores": errors})
            results.rechazadas += 1
            continue
        
        # 1) VALIDAR EMPRESA existe y activa
        empresa_val = row.get('empresa', '').strip().upper()
        empresa = empresas.get(empresa_val)
        if not empresa:
            errors.append({"columna": "empresa", "motivo": f"Empresa '{row.get('empresa')}' no existe"})
        elif not empresa.get('is_active', True):
            errors.append({"columna": "empresa", "motivo": f"Empresa '{row.get('empresa')}' está inactiva"})
        
        # 2) VALIDAR PROYECTO existe, activo y pertenece a empresa
        proyecto_val = row.get('proyecto', '').strip().upper()
        project = projects_by_code.get(proyecto_val) or projects_by_name.get(proyecto_val)
        if not project:
            errors.append({"columna": "proyecto", "motivo": f"Proyecto '{row.get('proyecto')}' no existe"})
        elif not project.get('is_active', True):
            errors.append({"columna": "proyecto", "motivo": f"Proyecto '{row.get('proyecto')}' está inactivo"})
        elif empresa and project.get('empresa_id') != empresa.get('id'):
            empresa_proyecto = empresas_by_id.get(project.get('empresa_id'), {})
            errors.append({"columna": "proyecto", "motivo": f"Proyecto '{row.get('proyecto')}' no pertenece a empresa '{row.get('empresa')}' (pertenece a '{empresa_proyecto.get('nombre', 'N/A')}')"})
        
        # 3) VALIDAR PARTIDA existe y activa en catalogo_partidas
        partida_val = row.get('partida', '').strip()
        partida = partidas_by_codigo.get(partida_val) or partidas_by_nombre.get(partida_val.upper())
        if not partida:
            errors.append({"columna": "partida", "motivo": f"Partida '{row.get('partida')}' no existe en catálogo"})
        elif not partida.get('is_active', True):
            errors.append({"columna": "partida", "motivo": f"Partida '{row.get('partida')}' está inactiva"})
        
        # 4) VALIDAR PROVEEDOR existe
        proveedor_val = row.get('proveedor', '').strip().upper()
        provider = providers_by_code.get(proveedor_val) or providers_by_name.get(proveedor_val)
        if not provider:
            errors.append({"columna": "proveedor", "motivo": f"Proveedor '{row.get('proveedor')}' no existe"})
        elif not provider.get('is_active', True):
            errors.append({"columna": "proveedor", "motivo": f"Proveedor '{row.get('proveedor')}' está inactivo"})
        
        # 5) VALIDAR MONTO > 0
        try:
            monto = float(row.get('monto', '0').replace(',', '').replace('$', '').strip())
            if monto <= 0:
                errors.append({"columna": "monto", "motivo": "Monto debe ser mayor a 0"})
        except ValueError:
            errors.append({"columna": "monto", "motivo": f"Monto '{row.get('monto')}' no es un número válido"})
            monto = 0
        
        # 6) VALIDAR MONEDA ∈ {MXN, USD}
        moneda = row.get('moneda', '').strip().upper()
        if moneda not in ['MXN', 'USD']:
            errors.append({"columna": "moneda", "motivo": f"Moneda '{row.get('moneda')}' no válida (solo MXN o USD)"})
        
        # 7) VALIDAR TIPO_CAMBIO si USD
        tipo_cambio_str = row.get('tipo_cambio', '').strip()
        tipo_cambio = 1.0
        if moneda == 'USD':
            if not tipo_cambio_str:
                errors.append({"columna": "tipo_cambio", "motivo": "USD requiere tipo_cambio obligatorio"})
            else:
                try:
                    tipo_cambio = float(tipo_cambio_str.replace(',', ''))
                    if tipo_cambio <= 0:
                        errors.append({"columna": "tipo_cambio", "motivo": "tipo_cambio debe ser mayor a 0"})
                except ValueError:
                    errors.append({"columna": "tipo_cambio", "motivo": f"tipo_cambio '{tipo_cambio_str}' no es válido"})
        elif moneda == 'MXN':
            tipo_cambio = 1.0
        
        # 8) VALIDAR FECHA - interpretar como America/Tijuana si no tiene hora
        fecha_str = row.get('fecha', '').strip()
        parsed_date = None
        try:
            parsed_date = parse_date_tijuana(fecha_str)
        except Exception as e:
            errors.append({"columna": "fecha", "motivo": f"Fecha '{fecha_str}' no válida (use formato YYYY-MM-DD o DD/MM/YYYY)"})
        
        # Si hay errores de validación, rechazar fila
        if errors:
            results.errores.append({"fila": row_num, "errores": errors})
            results.rechazadas += 1
            continue
        
        # 9) CHECK DUPLICADOS: fecha+empresa+proyecto+proveedor+monto+referencia
        referencia = row.get('referencia', '').strip()
        dup_query = {
            "date": parsed_date.isoformat(),
            "project_id": project['id'],
            "provider_id": provider['id'],
            "amount_original": monto,
            "reference": referencia
        }
        
        # También verificar si ya procesamos en este batch
        dup_key = f"{parsed_date.isoformat()}|{empresa['id']}|{project['id']}|{provider['id']}|{monto}|{referencia}"
        if dup_key in rows_processed:
            results.errores.append({"fila": row_num, "errores": [{"columna": "duplicado", "motivo": "Duplicado en el mismo archivo CSV"}]})
            results.duplicadas_omitidas += 1
            continue
        
        dup_check = await db.movements.find_one(dup_query, {"_id": 0})
        if dup_check:
            results.duplicadas_omitidas += 1
            continue  # Omitir silenciosamente como duplicado
        
        rows_processed.append(dup_key)
        
        # CALCULAR monto_mxn
        monto_mxn = monto * tipo_cambio
        
        # CHECK BUDGET para determinar si requiere autorización
        year = parsed_date.year
        month = parsed_date.month
        
        budget = await db.budgets.find_one({
            "project_id": project['id'],
            "partida_codigo": partida['codigo'],
            "year": year,
            "month": month
        }, {"_id": 0})
        
        current_movements = await db.movements.find({
            "project_id": project['id'],
            "partida_codigo": partida['codigo'],
            "status": MovementStatus.POSTED.value
        }, {"_id": 0}).to_list(5000)
        
        current_spent = sum(
            m['amount_mxn'] for m in current_movements
            if date_parser.parse(m['date']).year == year and date_parser.parse(m['date']).month == month
        )
        
        budget_amount = budget['amount_mxn'] if budget else 0
        new_total = current_spent + monto_mxn
        
        requires_auth = False
        auth_reason = ""
        percentage_if_posted = (new_total / budget_amount * 100) if budget_amount > 0 else 0
        
        if budget_amount == 0:
            requires_auth = True
            auth_reason = "Presupuesto no definido ($0) - requiere autorización"
        elif percentage_if_posted > 100:
            requires_auth = True
            auth_reason = f"Exceso de presupuesto: {percentage_if_posted:.1f}% (>100%)"
        
        # CREATE MOVEMENT
        descripcion = row.get('descripcion', '').strip() if row.get('descripcion') else None
        
        movement = Movement(
            project_id=project['id'],
            partida_codigo=partida['codigo'],
            provider_id=provider['id'],
            date=parsed_date,
            currency=Currency(moneda),
            amount_original=monto,
            exchange_rate=tipo_cambio,
            amount_mxn=monto_mxn,
            reference=referencia,
            description=descripcion,
            created_by=current_user["user_id"],
            status=MovementStatus.PENDING_APPROVAL if requires_auth else MovementStatus.POSTED
        )
        
        doc = movement.model_dump()
        doc['date'] = doc['date'].isoformat()
        doc['created_at'] = doc['created_at'].isoformat()
        
        if requires_auth:
            auth = Authorization(
                movement_id=movement.id,
                reason=auth_reason,
                requested_by=current_user["user_id"]
            )
            auth_doc = auth.model_dump()
            auth_doc['created_at'] = auth_doc['created_at'].isoformat()
            # Add budget context
            auth_doc['budget_context'] = {
                'partida_codigo': partida['codigo'],
                'presupuesto': budget_amount,
                'ejecutado_actual': current_spent,
                'monto_movimiento': monto_mxn,
                'porcentaje_actual': (current_spent / budget_amount * 100) if budget_amount > 0 else 0,
                'porcentaje_si_aprueba': percentage_if_posted
            }
            await db.authorizations.insert_one(auth_doc)
            doc['authorization_id'] = auth.id
            results.authorizations_required.append(movement.id)
        
        await db.movements.insert_one(doc)
        results.movements_created.append(movement.id)
        results.insertadas += 1
    
    # LOG AUDIT de import
    import_end = datetime.now(timezone.utc)
    errores_resumen = [f"Fila {e['fila']}: {'; '.join([err['motivo'] for err in e['errores']])}" for e in results.errores[:20]]
    
    import_audit = {
        "id": str(uuid.uuid4()),
        "user_id": current_user["user_id"],
        "user_email": current_user["email"],
        "action": "IMPORT_CSV",
        "timestamp_inicio": import_start.isoformat(),
        "timestamp_fin": import_end.isoformat(),
        "filtros": {"filename": file.filename},
        "conteos": {
            "total_filas": results.total_filas,
            "insertadas": results.insertadas,
            "rechazadas": results.rechazadas,
            "duplicadas_omitidas": results.duplicadas_omitidas
        },
        "errores_resumen": errores_resumen
    }
    await db.import_export_logs.insert_one(import_audit)
    
    await log_audit(current_user, "IMPORT_CSV", "movements", "batch", {
        "total_filas": results.total_filas,
        "insertadas": results.insertadas,
        "rechazadas": results.rechazadas,
        "duplicadas_omitidas": results.duplicadas_omitidas,
        "filename": file.filename
    })
    
    return results

# Keep legacy endpoint for backwards compatibility
@api_router.post("/movements/import")
async def import_movements_legacy(file: UploadFile = File(...), current_user: dict = Depends(require_permission(Permission.IMPORT_MOVEMENTS))):
    """Legacy import - redirects to new import-csv endpoint"""
    return await import_movements_csv(file, current_user)

# ========================= AUTHORIZATION ROUTES =========================
@api_router.get("/authorizations")
async def get_authorizations(
    status: Optional[str] = None,
    empresa_id: Optional[str] = None,
    project_id: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    current_user: dict = Depends(require_permission(Permission.VIEW_AUTHORIZATIONS))
):
    """Get authorizations with filters and enriched movement data"""
    query = {}
    if year:
        validate_year_in_range(year)
    if status:
        query["status"] = status
    
    auths = await db.authorizations.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    # Enrich with movement details
    project_docs = await db.projects.find({}, {"_id": 0}).to_list(1000)
    project_map = {p['id']: p for p in project_docs}
    
    empresa_docs = await db.empresas.find({}, {"_id": 0}).to_list(1000)
    empresa_map = {e['id']: e for e in empresa_docs}
    
    provider_docs = await db.providers.find({}, {"_id": 0}).to_list(1000)
    provider_map = {p['id']: p for p in provider_docs}
    
    partida_docs = await db.catalogo_partidas.find({}, {"_id": 0}).to_list(1000)
    partida_map = {p['codigo']: p for p in partida_docs}
    
    enriched_auths = []
    for auth in auths:
        movement = None
        if auth.get('movement_id'):
            movement = await db.movements.find_one({"id": auth['movement_id']}, {"_id": 0})
        
        if movement:
            project = project_map.get(movement.get('project_id'), {})
            empresa = empresa_map.get(project.get('empresa_id'), {})
            provider = provider_map.get(movement.get('provider_id'), {})
            partida = partida_map.get(movement.get('partida_codigo'), {})
            
            # Apply filters
            if empresa_id and empresa.get('id') != empresa_id:
                continue
            if project_id and project.get('id') != project_id:
                continue
            
            mov_date = date_parser.parse(movement['date'])
            if year and mov_date.year != year:
                continue
            if month and mov_date.month != month:
                continue
            
            auth['movement_details'] = {
                'date': movement.get('date'),
                'empresa_id': empresa.get('id'),
                'empresa_nombre': empresa.get('nombre', 'N/A'),
                'project_id': project.get('id'),
                'project_code': project.get('code', 'N/A'),
                'project_name': project.get('name', 'N/A'),
                'partida_codigo': movement.get('partida_codigo'),
                'partida_nombre': partida.get('nombre', 'N/A'),
                'provider_name': provider.get('name', 'N/A'),
                'moneda': movement.get('currency'),
                'monto_original': movement.get('amount_original'),
                'tipo_cambio': movement.get('exchange_rate'),
                'monto_mxn': movement.get('amount_mxn'),
                'referencia': movement.get('reference'),
                'descripcion': movement.get('description')
            }
        else:
            # Skip if no movement and filters are applied
            if empresa_id or project_id or year or month:
                continue
            auth['movement_details'] = None
        
        enriched_auths.append(auth)
    
    return enriched_auths

@api_router.get("/authorizations/pending-summary")
async def get_pending_summary(
    empresa_id: Optional[str] = None,
    project_id: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get summary of pending authorizations for dashboard KPI"""
    now = to_tijuana(datetime.now(timezone.utc))
    year = year or now.year
    validate_year_in_range(year)
    month = month or now.month
    
    # Get pending movements
    pending_query = {"status": MovementStatus.PENDING_APPROVAL.value}
    pending_movements = await db.movements.find(pending_query, {"_id": 0}).to_list(5000)
    
    # Filter by empresa/project/date
    project_docs = await db.projects.find({}, {"_id": 0}).to_list(1000)
    project_map = {p['id']: p for p in project_docs}
    
    filtered_pending = []
    for mov in pending_movements:
        project = project_map.get(mov.get('project_id'), {})
        
        if empresa_id and project.get('empresa_id') != empresa_id:
            continue
        if project_id and mov.get('project_id') != project_id:
            continue
        
        mov_date = date_parser.parse(mov['date'])
        if mov_date.year != year or mov_date.month != month:
            continue
        
        filtered_pending.append(mov)
    
    total_pending_mxn = sum(m.get('amount_mxn', 0) for m in filtered_pending)
    
    return {
        "pending_count": len(filtered_pending),
        "pending_total_mxn": total_pending_mxn,
        "year": year,
        "month": month
    }

@api_router.put("/authorizations/{auth_id}")
async def resolve_authorization(
    auth_id: str,
    resolution: AuthorizationResolve,
    current_user: dict = Depends(require_permission(Permission.APPROVE_REJECT))
):
    auth = await db.authorizations.find_one({"id": auth_id}, {"_id": 0})
    if not auth:
        raise HTTPException(status_code=404, detail="Autorización no encontrada")
    
    if auth['status'] != 'pending':
        raise HTTPException(status_code=400, detail="Autorización ya resuelta")
    
    # Reject requires notes/motivo
    if resolution.status == AuthorizationStatus.REJECTED and not resolution.notes:
        raise HTTPException(status_code=400, detail="Rechazo requiere motivo/notas")
    
    update_data = {
        "status": resolution.status.value,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "resolved_by": current_user["user_id"],
        "resolved_by_email": current_user["email"],
        "notes": resolution.notes
    }
    
    await db.authorizations.update_one({"id": auth_id}, {"$set": update_data})
    
    # Update movement status: approved -> posted, rejected -> rejected
    movement = None
    if auth.get('movement_id'):
        new_status = MovementStatus.POSTED if resolution.status == AuthorizationStatus.APPROVED else MovementStatus.REJECTED
        await db.movements.update_one(
            {"id": auth['movement_id']},
            {"$set": {"status": new_status.value}}
        )
        movement = await db.movements.find_one({"id": auth['movement_id']}, {"_id": 0})
    
    # Detailed audit log for approve/reject
    await log_audit(current_user, f"AUTH_{resolution.status.value.upper()}", "authorizations", auth_id, {
        "movement_id": auth.get('movement_id'),
        "resolution": resolution.status.value,
        "notes": resolution.notes,
        "amount_mxn": movement.get('amount_mxn') if movement else None,
        "partida_codigo": movement.get('partida_codigo') if movement else None,
        "budget_context": auth.get('budget_context')
    })
    
    return {"message": f"Autorización {resolution.status.value}"}

# ========================= REPORTS ROUTES =========================
@api_router.get("/reports/dashboard")
async def get_dashboard(
    empresa_id: Optional[str] = None,
    project_id: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    include_pending: bool = False,  # Toggle para ver posted vs total incluyendo pendientes
    current_user: dict = Depends(require_permission(Permission.VIEW_DASHBOARD))
):
    now = to_tijuana(datetime.now(timezone.utc))
    year = year or now.year
    validate_year_in_range(year)
    month = month or now.month
    
    # Get projects filtered by empresa
    project_query = {}
    if empresa_id:
        project_query["empresa_id"] = empresa_id
    all_projects = await db.projects.find(project_query, {"_id": 0}).to_list(1000)
    project_ids = [p['id'] for p in all_projects]
    
    # Get budgets
    budget_query = {"year": year, "month": month}
    if project_id:
        budget_query["project_id"] = project_id
    elif empresa_id:
        budget_query["project_id"] = {"$in": project_ids}
    
    budgets = await db.budgets.find(budget_query, {"_id": 0}).to_list(1000)
    
    # Get movements - SOLO posted por default (ejecutado real)
    posted_statuses = [MovementStatus.POSTED.value]
    if include_pending:
        posted_statuses.append(MovementStatus.PENDING_APPROVAL.value)
    
    movement_query = {"status": {"$in": posted_statuses}}
    if project_id:
        movement_query["project_id"] = project_id
    elif empresa_id:
        movement_query["project_id"] = {"$in": project_ids}
    
    all_movements = await db.movements.find(movement_query, {"_id": 0}).to_list(5000)
    
    # Filter by date
    movements = [
        m for m in all_movements
        if date_parser.parse(m['date']).year == year and date_parser.parse(m['date']).month == month
    ]
    
    # Get pending movements for KPI (separate query)
    pending_query = {"status": MovementStatus.PENDING_APPROVAL.value}
    if project_id:
        pending_query["project_id"] = project_id
    elif empresa_id:
        pending_query["project_id"] = {"$in": project_ids}
    
    all_pending = await db.movements.find(pending_query, {"_id": 0}).to_list(5000)
    pending_movements = [
        m for m in all_pending
        if date_parser.parse(m['date']).year == year and date_parser.parse(m['date']).month == month
    ]
    pending_total_mxn = sum(m['amount_mxn'] for m in pending_movements)
    pending_count = len(pending_movements)
    
    # Calculate totals
    total_budget = sum(b['amount_mxn'] for b in budgets)
    total_real = sum(m['amount_mxn'] for m in movements)
    variation = total_budget - total_real
    percentage = (total_real / total_budget * 100) if total_budget > 0 else 0
    
    # By partida (using partida_codigo from catalogo)
    partidas_data = {}
    for b in budgets:
        key = b.get('partida_codigo', b.get('partida_id', 'N/A'))
        if key not in partidas_data:
            partidas_data[key] = {"budget": 0, "real": 0}
        partidas_data[key]["budget"] += b['amount_mxn']
    
    for m in movements:
        key = m.get('partida_codigo', m.get('partida_id', 'N/A'))
        if key not in partidas_data:
            partidas_data[key] = {"budget": 0, "real": 0}
        partidas_data[key]["real"] += m['amount_mxn']
    
    # Get partida names from catalogo
    partida_docs = await db.catalogo_partidas.find({}, {"_id": 0}).to_list(1000)
    partida_map = {p['codigo']: p for p in partida_docs}
    
    partidas_summary = []
    for partida_codigo, data in partidas_data.items():
        pct = (data['real'] / data['budget'] * 100) if data['budget'] > 0 else (100 if data['real'] > 0 else 0)
        partida_info = partida_map.get(partida_codigo, {})
        partidas_summary.append({
            "partida_codigo": partida_codigo,
            "partida_nombre": partida_info.get('nombre', partida_codigo),
            "partida_grupo": partida_info.get('grupo', 'N/A'),
            "budget": data['budget'],
            "real": data['real'],
            "variation": data['budget'] - data['real'],
            "percentage": pct,
            "traffic_light": get_traffic_light(pct)
        })
    
    # By project
    projects_data = {}
    for b in budgets:
        key = b['project_id']
        if key not in projects_data:
            projects_data[key] = {"budget": 0, "real": 0}
        projects_data[key]["budget"] += b['amount_mxn']
    
    for m in movements:
        key = m['project_id']
        if key not in projects_data:
            projects_data[key] = {"budget": 0, "real": 0}
        projects_data[key]["real"] += m['amount_mxn']
    
    project_docs = await db.projects.find({}, {"_id": 0}).to_list(1000)
    project_map = {p['id']: p for p in project_docs}
    
    projects_summary = []
    for proj_id, data in projects_data.items():
        pct = (data['real'] / data['budget'] * 100) if data['budget'] > 0 else (100 if data['real'] > 0 else 0)
        proj_info = project_map.get(proj_id, {})
        projects_summary.append({
            "project_id": proj_id,
            "project_code": proj_info.get('code', 'N/A'),
            "project_name": proj_info.get('name', 'N/A'),
            "budget": data['budget'],
            "real": data['real'],
            "variation": data['budget'] - data['real'],
            "percentage": pct,
            "traffic_light": get_traffic_light(pct)
        })
    
    # Pending authorizations count (for badge in menu)
    pending_auths = await db.authorizations.count_documents({"status": "pending"})
    
    return {
        "year": year,
        "month": month,
        "totals": {
            "budget": total_budget,
            "real": total_real,
            "variation": variation,
            "percentage": percentage,
            "traffic_light": get_traffic_light(percentage)
        },
        "pending": {
            "count": pending_count,
            "total_mxn": pending_total_mxn
        },
        "by_partida": sorted(partidas_summary, key=lambda x: x['percentage'], reverse=True),
        "by_project": sorted(projects_summary, key=lambda x: x['percentage'], reverse=True),
        "pending_authorizations": pending_auths,
        "movements_count": len(movements),
        "include_pending": include_pending
    }

@api_router.get("/reports/partida-detail/{partida_codigo}")
async def get_partida_detail(
    partida_codigo: str,
    empresa_id: Optional[str] = None,
    project_id: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    now = to_tijuana(datetime.now(timezone.utc))
    year = year or now.year
    validate_year_in_range(year)
    month = month or now.month
    
    # Get partida from catalogo
    partida = await db.catalogo_partidas.find_one({"codigo": partida_codigo}, {"_id": 0})
    if not partida:
        raise HTTPException(status_code=404, detail=f"Partida {partida_codigo} no encontrada en catálogo")
    
    # Get projects filtered by empresa
    project_ids = None
    if empresa_id:
        projects = await db.projects.find({"empresa_id": empresa_id}, {"_id": 0}).to_list(1000)
        project_ids = [p['id'] for p in projects]
    
    # Get budgets
    budget_query = {"partida_codigo": partida_codigo, "year": year, "month": month}
    if project_id:
        budget_query["project_id"] = project_id
    elif project_ids:
        budget_query["project_id"] = {"$in": project_ids}
    
    budgets = await db.budgets.find(budget_query, {"_id": 0}).to_list(1000)
    total_budget = sum(b['amount_mxn'] for b in budgets)
    
    # Get movements - SOLO posted
    movement_query = {"partida_codigo": partida_codigo, "status": MovementStatus.POSTED.value}
    if project_id:
        movement_query["project_id"] = project_id
    elif project_ids:
        movement_query["project_id"] = {"$in": project_ids}
    
    all_movements = await db.movements.find(movement_query, {"_id": 0}).to_list(5000)
    movements = [
        m for m in all_movements
        if date_parser.parse(m['date']).year == year and date_parser.parse(m['date']).month == month
    ]
    
    total_real = sum(m['amount_mxn'] for m in movements)
    percentage = (total_real / total_budget * 100) if total_budget > 0 else (100 if total_real > 0 else 0)
    
    # Get provider names
    provider_docs = await db.providers.find({}, {"_id": 0}).to_list(1000)
    provider_map = {p['id']: p for p in provider_docs}
    
    # Get project names
    project_docs = await db.projects.find({}, {"_id": 0}).to_list(1000)
    project_map = {p['id']: p for p in project_docs}
    
    # Enrich movements
    for m in movements:
        prov = provider_map.get(m['provider_id'], {})
        proj = project_map.get(m['project_id'], {})
        m['provider_name'] = prov.get('name', 'N/A')
        m['project_name'] = proj.get('name', 'N/A')
    
    return {
        "partida": {"codigo": partida['codigo'], "nombre": partida['nombre'], "grupo": partida['grupo']},
        "year": year,
        "month": month,
        "budget": total_budget,
        "real": total_real,
        "variation": total_budget - total_real,
        "percentage": percentage,
        "traffic_light": get_traffic_light(percentage),
        "movements": sorted(movements, key=lambda x: x['date'], reverse=True)
    }

@api_router.get("/reports/export-data")
async def get_export_data(
    empresa_id: Optional[str] = None,
    project_id: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Returns data for Excel export with 2 sheets:
    - Hoja 1 "Resumen" (KPIs)
    - Hoja 2 "Detalle" (por partida + semáforo)
    All dates in America/Tijuana timezone.
    Logs export action to audit.
    """
    now = to_tijuana(datetime.now(timezone.utc))
    year = year or now.year
    validate_year_in_range(year)
    month = month or now.month
    
    # Get empresas for filter names
    empresas = await db.empresas.find({}, {"_id": 0}).to_list(1000)
    empresa_map = {e['id']: e for e in empresas}
    
    # Get projects filtered by empresa
    project_query = {}
    if empresa_id:
        project_query["empresa_id"] = empresa_id
    all_projects = await db.projects.find(project_query, {"_id": 0}).to_list(1000)
    project_ids = [p['id'] for p in all_projects]
    project_map = {p['id']: p for p in all_projects}
    
    # Get budgets
    budget_query = {"year": year, "month": month}
    if project_id:
        budget_query["project_id"] = project_id
    elif empresa_id:
        budget_query["project_id"] = {"$in": project_ids}
    
    budgets = await db.budgets.find(budget_query, {"_id": 0}).to_list(1000)
    
    # Get movements
    movement_query = {"status": {"$in": ["normal", "authorized"]}}
    if project_id:
        movement_query["project_id"] = project_id
    elif empresa_id:
        movement_query["project_id"] = {"$in": project_ids}
    
    all_movements = await db.movements.find(movement_query, {"_id": 0}).to_list(5000)
    
    # Filter by date
    movements = [
        m for m in all_movements
        if date_parser.parse(m['date']).year == year and date_parser.parse(m['date']).month == month
    ]
    
    # Calculate totals
    total_budget = sum(b['amount_mxn'] for b in budgets)
    total_real = sum(m['amount_mxn'] for m in movements)
    variation = total_budget - total_real
    percentage = (total_real / total_budget * 100) if total_budget > 0 else 0
    
    # By partida
    partidas_data = {}
    for b in budgets:
        key = b.get('partida_codigo', 'N/A')
        if key not in partidas_data:
            partidas_data[key] = {"budget": 0, "real": 0}
        partidas_data[key]["budget"] += b['amount_mxn']
    
    for m in movements:
        key = m.get('partida_codigo', 'N/A')
        if key not in partidas_data:
            partidas_data[key] = {"budget": 0, "real": 0}
        partidas_data[key]["real"] += m['amount_mxn']
    
    # Get partida info from catalogo
    partida_docs = await db.catalogo_partidas.find({}, {"_id": 0}).to_list(1000)
    partida_map = {p['codigo']: p for p in partida_docs}
    
    # Get providers
    provider_docs = await db.providers.find({}, {"_id": 0}).to_list(1000)
    provider_map = {p['id']: p for p in provider_docs}
    
    partidas_detail = []
    for partida_codigo, data in partidas_data.items():
        pct = (data['real'] / data['budget'] * 100) if data['budget'] > 0 else (100 if data['real'] > 0 else 0)
        partida_info = partida_map.get(partida_codigo, {})
        
        # Get movements for this partida
        partida_movements = [m for m in movements if m.get('partida_codigo') == partida_codigo]
        
        # Enrich movements with provider and project names, convert dates to Tijuana
        enriched_movements = []
        for mov in partida_movements:
            proj = project_map.get(mov['project_id'], {})
            prov = provider_map.get(mov['provider_id'], {})
            mov_date = date_parser.parse(mov['date'])
            mov_date_tj = to_tijuana(mov_date)
            
            enriched_movements.append({
                "fecha": mov_date_tj.strftime('%Y-%m-%d %H:%M'),
                "proyecto": proj.get('name', 'N/A'),
                "proveedor": prov.get('name', 'N/A'),
                "referencia": mov.get('reference', ''),
                "moneda": mov.get('currency', 'MXN'),
                "monto_original": mov.get('amount_original', 0),
                "tipo_cambio": mov.get('exchange_rate', 1),
                "monto_mxn": mov.get('amount_mxn', 0),
                "descripcion": mov.get('description', '')
            })
        
        partidas_detail.append({
            "codigo": partida_codigo,
            "nombre": partida_info.get('nombre', partida_codigo),
            "grupo": partida_info.get('grupo', 'N/A'),
            "presupuesto": data['budget'],
            "ejecutado": data['real'],
            "variacion": data['budget'] - data['real'],
            "porcentaje": pct,
            "semaforo": "Normal" if pct <= 90 else ("Alerta" if pct <= 100 else "Exceso"),
            "movimientos": sorted(enriched_movements, key=lambda x: x['fecha'], reverse=True)
        })
    
    # Build filter description
    filter_desc = {
        "empresa": empresa_map.get(empresa_id, {}).get('nombre', 'Todas') if empresa_id else "Todas",
        "proyecto": project_map.get(project_id, {}).get('name', 'Todos') if project_id else "Todos",
        "año": year,
        "mes": month
    }
    
    # LOG EXPORT to audit
    export_audit = {
        "id": str(uuid.uuid4()),
        "user_id": current_user["user_id"],
        "user_email": current_user["email"],
        "action": "EXPORT_EXCEL",
        "timestamp_inicio": datetime.now(timezone.utc).isoformat(),
        "timestamp_fin": datetime.now(timezone.utc).isoformat(),
        "filtros": filter_desc,
        "conteos": {
            "partidas": len(partidas_detail),
            "movimientos": len(movements),
            "total_presupuesto": total_budget,
            "total_ejecutado": total_real
        }
    }
    await db.import_export_logs.insert_one(export_audit)
    
    await log_audit(current_user, "EXPORT_EXCEL", "reports", "export", {"filtros": filter_desc})
    
    months_es = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    
    return {
        "filtros": filter_desc,
        "periodo": f"{months_es.get(month, month)} {year}",
        "resumen": {
            "presupuesto": total_budget,
            "ejecutado": total_real,
            "variacion": variation,
            "porcentaje": percentage,
            "semaforo": "Normal" if percentage <= 90 else ("Alerta" if percentage <= 100 else "Exceso")
        },
        "detalle_partidas": sorted(partidas_detail, key=lambda x: x['porcentaje'], reverse=True),
        "generated_at": to_tijuana(datetime.now(timezone.utc)).strftime('%Y-%m-%d %H:%M:%S'),
        "timezone": "America/Tijuana"
    }

@api_router.get("/import-export-logs")
async def get_import_export_logs(
    action: Optional[str] = None,
    limit: int = Query(50, le=500),
    current_user: dict = Depends(require_permission(Permission.VIEW_AUDIT))
):
    """Get import/export audit logs"""
    query = {}
    if action:
        query["action"] = action
    
    logs = await db.import_export_logs.find(query, {"_id": 0}).sort("timestamp_inicio", -1).to_list(limit)
    return logs

# ========================= AUDIT LOG ROUTES (ENHANCED P3.2) =========================
@api_router.get("/audit-logs")
async def get_audit_logs(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None,
    action: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(100, le=1000),
    current_user: dict = Depends(require_permission(Permission.VIEW_AUDIT))
):
    """Enhanced audit log with advanced filters"""
    query = {}
    if entity_type:
        query["entity_type"] = entity_type
    if entity_id:
        query["entity_id"] = entity_id
    if user_id:
        query["user_id"] = user_id
    if user_role:
        query["user_role"] = user_role
    if action:
        query["action"] = {"$regex": action, "$options": "i"}
    
    # Date range filter
    if date_from or date_to:
        query["timestamp"] = {}
        if date_from:
            query["timestamp"]["$gte"] = date_from
        if date_to:
            query["timestamp"]["$lte"] = date_to + "T23:59:59"
    
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return logs

@api_router.get("/audit-logs/export-csv")
async def export_audit_logs_csv(
    entity_type: Optional[str] = None,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(5000, le=10000),
    current_user: dict = Depends(require_permission(Permission.EXPORT_AUDIT))
):
    """Export audit log to CSV (Admin only)"""
    query = {}
    if entity_type:
        query["entity_type"] = entity_type
    if user_id:
        query["user_id"] = user_id
    if action:
        query["action"] = {"$regex": action, "$options": "i"}
    if date_from or date_to:
        query["timestamp"] = {}
        if date_from:
            query["timestamp"]["$gte"] = date_from
        if date_to:
            query["timestamp"]["$lte"] = date_to + "T23:59:59"
    
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    
    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Usuario", "Email", "Rol", "Acción", "Entidad", "Entity ID", "Cambios"])
    
    for log in logs:
        changes_str = str(log.get('changes', {}))[:200]  # Truncate changes for CSV
        writer.writerow([
            log.get('timestamp', ''),
            log.get('user_id', ''),
            log.get('user_email', ''),
            log.get('user_role', ''),
            log.get('action', ''),
            log.get('entity_type', ''),
            log.get('entity_id', ''),
            changes_str
        ])
    
    await log_audit(current_user, "EXPORT_AUDIT_CSV", "audit_logs", "export", {
        "filters": {"entity_type": entity_type, "user_id": user_id, "action": action, "date_from": date_from, "date_to": date_to},
        "count": len(logs)
    })
    
    return {
        "csv_content": output.getvalue(),
        "filename": f"audit_log_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv",
        "count": len(logs)
    }

@api_router.get("/audit-logs/summary")
async def get_audit_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: dict = Depends(require_permission(Permission.VIEW_AUDIT))
):
    """Get audit log summary for dashboard"""
    query = {}
    if date_from or date_to:
        query["timestamp"] = {}
        if date_from:
            query["timestamp"]["$gte"] = date_from
        if date_to:
            query["timestamp"]["$lte"] = date_to + "T23:59:59"
    
    logs = await db.audit_logs.find(query, {"_id": 0}).to_list(5000)
    
    # Count by action
    by_action = {}
    by_user = {}
    by_entity = {}
    
    for log in logs:
        action = log.get('action', 'UNKNOWN')
        user = log.get('user_email', 'N/A')
        entity = log.get('entity_type', 'N/A')
        
        by_action[action] = by_action.get(action, 0) + 1
        by_user[user] = by_user.get(user, 0) + 1
        by_entity[entity] = by_entity.get(entity, 0) + 1
    
    return {
        "total_logs": len(logs),
        "by_action": dict(sorted(by_action.items(), key=lambda x: x[1], reverse=True)[:20]),
        "by_user": dict(sorted(by_user.items(), key=lambda x: x[1], reverse=True)[:10]),
        "by_entity": dict(sorted(by_entity.items(), key=lambda x: x[1], reverse=True)[:10])
    }

@api_router.get("/rbac/permissions-matrix")
async def get_permissions_matrix(current_user: dict = Depends(require_permission(Permission.VIEW_AUDIT))):
    """Return the RBAC permissions matrix for documentation"""
    return {
        "roles": [r.value for r in UserRole],
        "permissions": [p.value for p in Permission],
        "matrix": {role: perms for role, perms in ROLE_PERMISSIONS.items()}
    }

# ========================= CONFIG ROUTES =========================
@api_router.get("/config")
async def get_config(current_user: dict = Depends(require_permission(Permission.VIEW_CATALOGS))):
    configs = await db.config.find({}, {"_id": 0}).to_list(100)
    return {c['key']: c['value'] for c in configs}

@api_router.put("/config/{key}")
async def update_config(key: str, value: Any, current_user: dict = Depends(require_permission(Permission.MANAGE_CATALOGS))):
    existing = await db.config.find_one({"key": key}, {"_id": 0})
    
    if existing:
        old_value = existing['value']
        await db.config.update_one(
            {"key": key},
            {"$set": {"value": value, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": current_user["user_id"]}}
        )
    else:
        config = ConfigSetting(key=key, value=value, updated_by=current_user["user_id"])
        doc = config.model_dump()
        doc['updated_at'] = doc['updated_at'].isoformat()
        await db.config.insert_one(doc)
        old_value = None
    
    await log_audit(current_user, "UPDATE", "config", key, {"before": old_value, "after": value})
    return {"message": "Configuración actualizada"}

# ========================= DATA MIGRATION =========================
@api_router.post("/migrate-movement-status")
async def migrate_movement_status():
    """Migrate old movement statuses to new format: normal/authorized -> posted"""
    # Update normal -> posted
    result_normal = await db.movements.update_many(
        {"status": "normal"},
        {"$set": {"status": MovementStatus.POSTED.value}}
    )
    
    # Update authorized -> posted
    result_auth = await db.movements.update_many(
        {"status": "authorized"},
        {"$set": {"status": MovementStatus.POSTED.value}}
    )
    
    # Update pending_authorization -> pending_approval
    result_pending = await db.movements.update_many(
        {"status": "pending_authorization"},
        {"$set": {"status": MovementStatus.PENDING_APPROVAL.value}}
    )
    
    return {
        "migrated": {
            "normal_to_posted": result_normal.modified_count,
            "authorized_to_posted": result_auth.modified_count,
            "pending_authorization_to_pending_approval": result_pending.modified_count
        }
    }

# ========================= DEMO DATA =========================
ADMIN_ENTITY_COLLECTIONS = {
    "empresas": ("empresas", [("nombre", 1)]),
    "proyectos": ("projects", [("name", 1)]),
    "catalogo_partidas": ("catalogo_partidas", [("codigo", 1)]),
    "proveedores": ("providers", [("name", 1)]),
    "usuarios": ("users", [("name", 1)]),
}

ADMIN_CATALOGOS_ALIAS = {
    "e": "empresas",
    "p": "proyectos",
    "c": "catalogo_partidas",
    "d": "proveedores",
    "u": "usuarios",
}



@api_router.get("/admin/catalogs/{entity}")
async def admin_list_entity(
    entity: str,
    include_inactive: bool = False,
    current_user: dict = Depends(require_permission(Permission.MANAGE_USERS)),
):
    ensure_admin(current_user)
    if entity not in ADMIN_ENTITY_COLLECTIONS:
        raise HTTPException(status_code=404, detail="Entidad admin no soportada")

    collection, sort = ADMIN_ENTITY_COLLECTIONS[entity]
    query = active_query(include_inactive)
    projection = {"_id": 0}
    if collection == "users":
        projection["password_hash"] = 0
    cursor = db[collection].find(query, projection)
    if sort:
        cursor = cursor.sort(sort)
    return await cursor.to_list(1000)


@api_router.get("/admin/users")
async def admin_find_users(
    email: Optional[str] = None,
    username: Optional[str] = None,
    include_inactive: bool = True,
    current_user: dict = Depends(require_permission(Permission.MANAGE_USERS)),
):
    ensure_admin(current_user)
    if not email and not username:
        raise HTTPException(status_code=400, detail="Debes enviar email o username")

    filters = []
    if email:
        filters.append({"email": email})
    if username:
        filters.append({"name": username})

    query = {"$or": filters} if len(filters) > 1 else filters[0]
    if not include_inactive:
        query["is_active"] = {"$ne": False}

    users = await db.users.find(query, {"_id": 0, "password_hash": 0}).to_list(50)
    return users


class AdminPasswordUpdate(BaseModel):
    password: str


@api_router.patch("/admin/users/{user_id}/password")
async def admin_update_user_password(
    user_id: str,
    payload: AdminPasswordUpdate,
    request: Request,
    current_user: dict = Depends(require_permission(Permission.MANAGE_USERS)),
):
    ensure_admin(current_user)
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "password_hash": hash_password(payload.password),
            "must_change_password": True,
            "is_active": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    updated = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    await log_admin_action(request, current_user, "ADMIN_RESET_PASSWORD", "users", user_id, True, after=updated)
    return {"message": "Contraseña actualizada", "user": updated}


@api_router.get("/admin/catalogos/{tipo}")
async def admin_catalogos_alias(
    tipo: str,
    de_inactive: bool = False,
    current_user: dict = Depends(require_permission(Permission.MANAGE_USERS)),
):
    mapped_entity = ADMIN_CATALOGOS_ALIAS.get(tipo, tipo)
    return await admin_list_entity(mapped_entity, include_inactive=de_inactive, current_user=current_user)


@api_router.get("/admin/catalogos/{tipo}_de_inactive={de_inactive}")
async def admin_catalogos_legacy_path(
    tipo: str,
    de_inactive: bool,
    current_user: dict = Depends(require_permission(Permission.MANAGE_USERS)),
):
    mapped_entity = ADMIN_CATALOGOS_ALIAS.get(tipo, tipo)
    return await admin_list_entity(mapped_entity, include_inactive=de_inactive, current_user=current_user)


@api_router.post("/admin/catalogs/{entity}")
async def admin_create_entity(
    entity: str,
    payload: dict,
    request: Request,
    current_user: dict = Depends(require_permission(Permission.MANAGE_USERS)),
):
    ensure_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()
    if entity not in ADMIN_ENTITY_COLLECTIONS:
        raise HTTPException(status_code=404, detail="Entidad admin no soportada")

    collection = ADMIN_ENTITY_COLLECTIONS[entity][0]
    doc = payload.copy()
    doc["id"] = doc.get("id") or str(uuid.uuid4())
    doc.setdefault("is_active", True)
    doc.setdefault("created_at", now)
    doc.setdefault("updated_at", now)

    if collection == "users":
        password = doc.pop("password", None)
        if not password:
            raise HTTPException(status_code=400, detail="password es requerido")
        if not doc.get("email"):
            raise HTTPException(status_code=400, detail="email es requerido")
        if not doc.get("name"):
            raise HTTPException(status_code=400, detail="name es requerido")
        role = doc.get("role")
        try:
            doc["role"] = UserRole(role).value
        except Exception:
            allowed = ", ".join([r.value for r in UserRole])
            raise HTTPException(status_code=400, detail=f"role inválido. Valores permitidos: {allowed}")

        is_active_raw = doc.get("is_active", True)
        if isinstance(is_active_raw, str):
            lower = is_active_raw.strip().lower()
            if lower in {"true", "1", "yes", "si", "sí"}:
                doc["is_active"] = True
            elif lower in {"false", "0", "no"}:
                doc["is_active"] = False
            else:
                raise HTTPException(status_code=400, detail="is_active debe ser booleano (true/false)")
        else:
            doc["is_active"] = bool(is_active_raw)

        doc["password_hash"] = hash_password(password)
        doc["must_change_password"] = True

    try:
        await db[collection].insert_one(doc)
    except DuplicateKeyError:
        if collection == "users":
            raise HTTPException(status_code=409, detail="Ya existe un usuario con ese email")
        raise HTTPException(status_code=409, detail="Registro duplicado")
    await log_admin_action(request, current_user, "ADMIN_CREATE", entity, doc["id"], True, after={k: v for k, v in doc.items() if k != "password_hash"})
    doc.pop("password_hash", None)
    return doc


@api_router.put("/admin/catalogs/{entity}/{entity_id}")
async def admin_update_entity(
    entity: str,
    entity_id: str,
    payload: dict,
    request: Request,
    current_user: dict = Depends(require_permission(Permission.MANAGE_USERS)),
):
    ensure_admin(current_user)
    if entity not in ADMIN_ENTITY_COLLECTIONS:
        raise HTTPException(status_code=404, detail="Entidad admin no soportada")

    collection = ADMIN_ENTITY_COLLECTIONS[entity][0]
    old_doc = await db[collection].find_one({"id": entity_id}, {"_id": 0})
    if not old_doc:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    if collection == "users" and "role" in payload and old_doc.get("role") == UserRole.ADMIN.value and payload.get("role") != UserRole.ADMIN.value:
        admins = await db.users.count_documents({"role": UserRole.ADMIN.value, "is_active": {"$ne": False}})
        if admins <= 1:
            raise HTTPException(status_code=409, detail="No puedes quitar el último admin")

    if collection == "users" and "password" in payload:
        payload["password_hash"] = hash_password(payload.pop("password"))
        payload["must_change_password"] = True

    if collection == "users" and "role" in payload:
        try:
            payload["role"] = UserRole(payload.get("role")).value
        except Exception:
            allowed = ", ".join([r.value for r in UserRole])
            raise HTTPException(status_code=400, detail=f"role inválido. Valores permitidos: {allowed}")

    if collection == "users" and "is_active" in payload and isinstance(payload.get("is_active"), str):
        lower = payload.get("is_active").strip().lower()
        if lower in {"true", "1", "yes", "si", "sí"}:
            payload["is_active"] = True
        elif lower in {"false", "0", "no"}:
            payload["is_active"] = False
        else:
            raise HTTPException(status_code=400, detail="is_active debe ser booleano (true/false)")

    if entity == "catalogo_partidas" and old_doc.get("codigo") != payload.get("codigo", old_doc.get("codigo")):
        raise HTTPException(status_code=400, detail="No se permite cambiar código de partida")

    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        await db[collection].update_one({"id": entity_id}, {"$set": payload})
    except DuplicateKeyError:
        if collection == "users":
            raise HTTPException(status_code=409, detail="Ya existe un usuario con ese email")
        raise HTTPException(status_code=409, detail="Registro duplicado")
    updated = await db[collection].find_one({"id": entity_id}, {"_id": 0})

    await log_admin_action(
        request,
        current_user,
        "ADMIN_UPDATE",
        entity,
        entity_id,
        True,
        before={k: v for k, v in old_doc.items() if k != "password_hash"},
        after={k: v for k, v in updated.items() if k != "password_hash"},
    )
    updated.pop("password_hash", None)
    return updated


@api_router.delete("/admin/catalogs/{entity}/{entity_id}")
async def admin_delete_entity(
    entity: str,
    entity_id: str,
    hard_delete: bool = False,
    request: Request = None,
    current_user: dict = Depends(require_permission(Permission.MANAGE_USERS)),
):
    ensure_admin(current_user)
    collection_map = {
        "empresas": "empresas",
        "proyectos": "projects",
        "catalogo_partidas": "catalogo_partidas",
        "proveedores": "providers",
        "usuarios": "users",
    }
    if entity not in collection_map:
        raise HTTPException(status_code=404, detail="Entidad admin no soportada")
    collection = collection_map[entity]

    old_doc = await db[collection].find_one({"id": entity_id}, {"_id": 0})
    if not old_doc:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    if hard_delete:
        await assert_no_references(entity, entity_id)
        await db[collection].delete_one({"id": entity_id})
        if request:
            await log_admin_action(request, current_user, "ADMIN_HARD_DELETE", entity, entity_id, True, before={k: v for k, v in old_doc.items() if k != "password_hash"})
        return {"message": "Eliminado físicamente"}

    await db[collection].update_one({"id": entity_id}, {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()}})
    if request:
        await log_admin_action(request, current_user, "ADMIN_SOFT_DELETE", entity, entity_id, True, before={k: v for k, v in old_doc.items() if k != "password_hash"}, after={"is_active": False})
    return {"message": "Desactivado"}


@api_router.post("/admin/catalogs/{entity}/{entity_id}/restore")
async def admin_restore_entity(
    entity: str,
    entity_id: str,
    request: Request,
    current_user: dict = Depends(require_permission(Permission.MANAGE_USERS)),
):
    ensure_admin(current_user)
    collection_map = {
        "empresas": "empresas",
        "proyectos": "projects",
        "catalogo_partidas": "catalogo_partidas",
        "proveedores": "providers",
        "usuarios": "users",
    }
    if entity not in collection_map:
        raise HTTPException(status_code=404, detail="Entidad admin no soportada")
    collection = collection_map[entity]

    old_doc = await db[collection].find_one({"id": entity_id}, {"_id": 0})
    if not old_doc:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    await db[collection].update_one({"id": entity_id}, {"$set": {"is_active": True, "updated_at": datetime.now(timezone.utc).isoformat()}})
    await log_admin_action(request, current_user, "ADMIN_RESTORE", entity, entity_id, True, before={"is_active": old_doc.get("is_active", True)}, after={"is_active": True})
    return {"message": "Restaurado"}


@api_router.get("/admin/movimientos")
async def admin_get_movimientos(
    include_inactive: bool = False,
    current_user: dict = Depends(require_permission(Permission.MANAGE_USERS)),
):
    ensure_admin(current_user)
    return await db.movements.find(active_query(include_inactive), {"_id": 0}).sort("created_at", -1).to_list(1000)


@api_router.put("/admin/movimientos/{movement_id}")
async def admin_update_movimiento(
    movement_id: str,
    payload: dict,
    request: Request,
    current_user: dict = Depends(require_permission(Permission.MANAGE_USERS)),
):
    ensure_admin(current_user)
    old_doc = await db.movements.find_one({"id": movement_id}, {"_id": 0})
    if not old_doc:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    if old_doc.get("status") == MovementStatus.POSTED.value:
        raise HTTPException(status_code=409, detail="Movimiento posted no se puede editar")

    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.movements.update_one({"id": movement_id}, {"$set": payload})
    updated = await db.movements.find_one({"id": movement_id}, {"_id": 0})
    await log_admin_action(request, current_user, "ADMIN_UPDATE", "movimientos", movement_id, True, before=old_doc, after=updated)
    return updated


@api_router.delete("/admin/movimientos/{movement_id}")
async def admin_delete_movimiento(
    movement_id: str,
    request: Request,
    current_user: dict = Depends(require_permission(Permission.MANAGE_USERS)),
):
    ensure_admin(current_user)
    mov = await db.movements.find_one({"id": movement_id}, {"_id": 0})
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    if mov.get("status") == MovementStatus.POSTED.value:
        raise HTTPException(status_code=409, detail="Movimiento posted no se puede borrar")

    await db.movements.update_one({"id": movement_id}, {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()}})
    await log_admin_action(request, current_user, "ADMIN_SOFT_DELETE", "movimientos", movement_id, True, before=mov, after={"is_active": False})
    return {"message": "Movimiento desactivado"}


@api_router.post("/admin/movimientos/{movement_id}/reverse")
async def admin_reverse_movement(
    movement_id: str,
    request: Request,
    current_user: dict = Depends(require_permission(Permission.MANAGE_USERS)),
):
    ensure_admin(current_user)
    movement = await db.movements.find_one({"id": movement_id}, {"_id": 0})
    if not movement:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    if movement.get("status") != MovementStatus.POSTED.value:
        raise HTTPException(status_code=409, detail="Solo movimientos posted pueden revertirse")

    existing_reversal = await db.movements.find_one({"reversal_of_id": movement_id}, {"_id": 0})
    if existing_reversal:
        raise HTTPException(status_code=409, detail="Movimiento ya tiene reversa")

    reverse_doc = movement.copy()
    reverse_doc["id"] = str(uuid.uuid4())
    reverse_doc["amount_original"] = -abs(float(movement.get("amount_original", 0)))
    reverse_doc["amount_mxn"] = -abs(float(movement.get("amount_mxn", 0)))
    reverse_doc["reference"] = f"REV-{movement.get('reference', movement_id)}"
    reverse_doc["description"] = f"Reversa de {movement_id}. {movement.get('description','')}".strip()
    reverse_doc["created_at"] = datetime.now(timezone.utc).isoformat()
    reverse_doc["created_by"] = current_user["user_id"]
    reverse_doc["reversal_of_id"] = movement_id
    reverse_doc["is_active"] = True

    await db.movements.insert_one(reverse_doc)
    await log_admin_action(request, current_user, "ADMIN_REVERSE", "movimientos", reverse_doc["id"], True, before=movement, after=reverse_doc)
    return reverse_doc


# Include router
app.include_router(api_router)

# CORS
raw_cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000')
cors_origins = [origin.strip() for origin in raw_cors_origins.split(',') if origin.strip()]
allow_all_origins = '*' in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_credentials=not allow_all_origins,
    allow_origins=['*'] if allow_all_origins else cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
