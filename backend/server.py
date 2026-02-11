from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========================= ENUMS =========================
class UserRole(str, Enum):
    ADMIN = "admin"
    FINANZAS = "finanzas"
    AUTORIZADOR = "autorizador"
    SOLO_LECTURA = "solo_lectura"

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

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User

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

def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc).timestamp() + 86400 * 7
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
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
        Permission.VIEW_AUTHORIZATIONS.value,  # Can view but NOT approve/reject
        Permission.VIEW_CATALOGS.value,
        Permission.VIEW_BUDGETS.value,
        Permission.MANAGE_BUDGETS.value,  # Can manage budgets
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

# ========================= AUTH ROUTES =========================
@api_router.post("/auth/register", response_model=User)
async def register(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    
    user = User(**user_data.model_dump(exclude={"password"}))
    doc = user.model_dump()
    doc['password_hash'] = hash_password(user_data.password)
    doc['created_at'] = doc['created_at'].isoformat()
    await db.users.insert_one(doc)
    return user

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user_doc = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user_doc or not verify_password(credentials.password, user_doc.get('password_hash', '')):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    if not user_doc.get('is_active', True):
        raise HTTPException(status_code=401, detail="Usuario desactivado")
    
    token = create_token(user_doc['id'], user_doc['email'], user_doc['role'])
    user = User(**{k: v for k, v in user_doc.items() if k != 'password_hash'})
    
    # Log successful login
    await log_audit(
        {"user_id": user_doc['id'], "email": user_doc['email'], "role": user_doc['role']},
        "LOGIN",
        "auth",
        user_doc['id'],
        {"status": "success"}
    )
    
    return TokenResponse(access_token=token, user=user)

@api_router.post("/auth/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Log user logout"""
    await log_audit(current_user, "LOGOUT", "auth", current_user["user_id"], {"status": "success"})
    return {"message": "Sesión cerrada"}

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
async def get_providers(current_user: dict = Depends(require_permission(Permission.VIEW_CATALOGS))):
    providers = await db.providers.find({}, {"_id": 0}).to_list(1000)
    return [Provider(**p) for p in providers]

@api_router.post("/providers", response_model=Provider)
async def create_provider(provider_data: ProviderBase, current_user: dict = Depends(require_permission(Permission.MANAGE_CATALOGS))):
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
async def import_movements_csv(file: UploadFile = File(...), current_user: dict = Depends(require_roles(UserRole.ADMIN, UserRole.FINANZAS))):
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
async def import_movements_legacy(file: UploadFile = File(...), current_user: dict = Depends(require_roles(UserRole.ADMIN, UserRole.FINANZAS))):
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
    current_user: dict = Depends(get_current_user)
):
    """Get authorizations with filters and enriched movement data"""
    query = {}
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
    current_user: dict = Depends(require_roles(UserRole.ADMIN, UserRole.AUTORIZADOR))
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
    if auth.get('movement_id'):
        new_status = MovementStatus.POSTED if resolution.status == AuthorizationStatus.APPROVED else MovementStatus.REJECTED
        await db.movements.update_one(
            {"id": auth['movement_id']},
            {"$set": {"status": new_status.value}}
        )
    
    # Detailed audit log for approve/reject
    await log_audit(current_user, f"AUTH_{resolution.status.value.upper()}", "authorizations", auth_id, {
        "movement_id": auth.get('movement_id'),
        "resolution": resolution.status.value,
        "notes": resolution.notes,
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
    current_user: dict = Depends(get_current_user)
):
    now = to_tijuana(datetime.now(timezone.utc))
    year = year or now.year
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
    current_user: dict = Depends(require_roles(UserRole.ADMIN, UserRole.AUTORIZADOR))
):
    """Get import/export audit logs"""
    query = {}
    if action:
        query["action"] = action
    
    logs = await db.import_export_logs.find(query, {"_id": 0}).sort("timestamp_inicio", -1).to_list(limit)
    return logs

# ========================= AUDIT LOG ROUTES =========================
@api_router.get("/audit-logs")
async def get_audit_logs(
    entity: Optional[str] = None,
    entity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = Query(100, le=1000),
    current_user: dict = Depends(require_roles(UserRole.ADMIN, UserRole.AUTORIZADOR))
):
    query = {}
    if entity:
        query["entity"] = entity
    if entity_id:
        query["entity_id"] = entity_id
    if user_id:
        query["user_id"] = user_id
    
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return logs

# ========================= CONFIG ROUTES =========================
@api_router.get("/config")
async def get_config(current_user: dict = Depends(get_current_user)):
    configs = await db.config.find({}, {"_id": 0}).to_list(100)
    return {c['key']: c['value'] for c in configs}

@api_router.put("/config/{key}")
async def update_config(key: str, value: Any, current_user: dict = Depends(require_roles(UserRole.ADMIN))):
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
@api_router.post("/seed-demo-data")
async def seed_demo_data():
    """Seed demo data: 3 empresas, 2 proyectos por empresa, catálogo real de partidas"""
    import random
    
    # Clear existing data
    await db.users.delete_many({})
    await db.empresas.delete_many({})
    await db.projects.delete_many({})
    await db.catalogo_partidas.delete_many({})
    await db.partidas.delete_many({})
    await db.providers.delete_many({})
    await db.budgets.delete_many({})
    await db.movements.delete_many({})
    await db.authorizations.delete_many({})
    await db.exchange_rates.delete_many({})
    await db.audit_logs.delete_many({})
    await db.config.delete_many({})
    await db.import_export_logs.delete_many({})
    
    # Create users
    users_data = [
        {"email": "admin@finrealty.com", "name": "Carlos Admin", "role": "admin", "password": "admin123"},
        {"email": "finanzas@finrealty.com", "name": "María Finanzas", "role": "finanzas", "password": "finanzas123"},
        {"email": "autorizador@finrealty.com", "name": "Roberto Autorizador", "role": "autorizador", "password": "auth123"},
        {"email": "lectura@finrealty.com", "name": "Ana Lectura", "role": "solo_lectura", "password": "lectura123"},
    ]
    
    for u in users_data:
        user = User(email=u['email'], name=u['name'], role=UserRole(u['role']))
        doc = user.model_dump()
        doc['password_hash'] = hash_password(u['password'])
        doc['created_at'] = doc['created_at'].isoformat()
        await db.users.insert_one(doc)
    
    # Create 3 empresas
    empresas_data = [
        {"nombre": "Altitud 3"},
        {"nombre": "Terraviva Desarrollos"},
        {"nombre": "Grupo Q"},
    ]
    
    empresa_ids = {}
    for e in empresas_data:
        empresa = Empresa(**e)
        empresa_ids[e['nombre']] = empresa.id
        doc = empresa.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        doc['updated_at'] = doc['updated_at'].isoformat()
        await db.empresas.insert_one(doc)
    
    # Create CATÁLOGO REAL DE PARTIDAS (source of truth)
    def get_grupo(codigo):
        cod = int(codigo)
        if 100 <= cod <= 199:
            return "obra"
        elif 200 <= cod <= 299:
            return "gya"
        elif 300 <= cod <= 399:
            return "financieros"
        elif 400 <= cod <= 499:
            return "ingresos"
        return "obra"
    
    catalogo_partidas_data = [
        {"codigo": "100", "nombre": "COSTO DIRECTO"},
        {"codigo": "101", "nombre": "TERRENO"},
        {"codigo": "102", "nombre": "PROYECTOS"},
        {"codigo": "103", "nombre": "LICENCIAS Y PERMISOS"},
        {"codigo": "104", "nombre": "EDIFICACION"},
        {"codigo": "105", "nombre": "URBANIZACION"},
        {"codigo": "106", "nombre": "INDIRECTOS DE OBRA"},
        {"codigo": "107", "nombre": "ACCESO"},
        {"codigo": "108", "nombre": "AMENIDADES"},
        {"codigo": "109", "nombre": "OFICINAS DE VENTAS"},
        {"codigo": "110", "nombre": "IMPREVISTOS"},
        {"codigo": "111", "nombre": "OBRAS CABECERAS"},
        {"codigo": "200", "nombre": "GASTOS DE VENTA Y ADMINISTRACION"},
        {"codigo": "201", "nombre": "GASTOS DE PUBLICIDAD Y PROMOCION"},
        {"codigo": "202", "nombre": "ACONDICIONAMIENTO DE MUESTRAS"},
        {"codigo": "203", "nombre": "COMISIONES SOBRE VENTA"},
        {"codigo": "204", "nombre": "DIRECCION DE PROYECTO"},
        {"codigo": "205", "nombre": "GASTOS ADMINISTRATIVOS"},
        {"codigo": "206", "nombre": "DOCUM TECNICA"},
        {"codigo": "207", "nombre": "GARANTIAS Y POSTVENTA"},
        {"codigo": "300", "nombre": "GASTOS FINANCIEROS"},
        {"codigo": "301", "nombre": "COMISIONES BANCARIAS"},
        {"codigo": "302", "nombre": "INTERESES"},
        {"codigo": "303", "nombre": "AMORTIZACION"},
        {"codigo": "400", "nombre": "INGRESOS"},
        {"codigo": "401", "nombre": "PRESTAMOS SOCIOS"},
        {"codigo": "402", "nombre": "ENGANCHES"},
        {"codigo": "403", "nombre": "INDIVIDUALIZACION"},
        {"codigo": "404", "nombre": "CREDITOS"},
    ]
    
    partida_codigos = []
    for p in catalogo_partidas_data:
        partida = CatalogoPartida(
            codigo=p['codigo'],
            nombre=p['nombre'],
            grupo=PartidaGrupo(get_grupo(p['codigo']))
        )
        partida_codigos.append(p['codigo'])
        doc = partida.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        doc['updated_at'] = doc['updated_at'].isoformat()
        await db.catalogo_partidas.insert_one(doc)
    
    # Create projects (2 per empresa = 6 total, but we'll use 2 for demo)
    projects_data = [
        {"code": "TORRE-A", "name": "Torre Altavista", "empresa": "Altitud 3", "description": "Desarrollo residencial premium 25 pisos"},
        {"code": "PLAZA-M", "name": "Plaza Comercial Marina", "empresa": "Terraviva Desarrollos", "description": "Centro comercial frente al mar"},
    ]
    
    project_ids = {}
    for p in projects_data:
        project = Project(
            code=p['code'],
            name=p['name'],
            empresa_id=empresa_ids[p['empresa']],
            description=p['description']
        )
        project_ids[p['code']] = project.id
        doc = project.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.projects.insert_one(doc)
    
    # Create 15 providers
    providers_data = [
        {"code": "CEMEX", "name": "CEMEX SA de CV", "rfc": "CEM123456ABC"},
        {"code": "ELECT", "name": "Electrificaciones del Norte", "rfc": "EDN789012DEF"},
        {"code": "HIDRO", "name": "Hidro Instalaciones Plus", "rfc": "HIP345678GHI"},
        {"code": "ACERO", "name": "Aceros y Derivados SA", "rfc": "AYD901234JKL"},
        {"code": "PINTA", "name": "Pinturas Premium MX", "rfc": "PPM567890MNO"},
        {"code": "ELEVA", "name": "Elevadores Schindler", "rfc": "ESM234567PQR"},
        {"code": "VIDRI", "name": "Vidriería Industrial", "rfc": "VID456789STU"},
        {"code": "CARPI", "name": "Carpintería Fina", "rfc": "CAR789012VWX"},
        {"code": "PLOME", "name": "Plomería Total", "rfc": "PLO012345YZA"},
        {"code": "AIRAC", "name": "Aires Acondicionados Pro", "rfc": "AAP345678BCD"},
        {"code": "SEGUV", "name": "Seguridad Vigilancia", "rfc": "SEG678901EFG"},
        {"code": "TRANS", "name": "Transportes Pesados MX", "rfc": "TRA901234HIJ"},
        {"code": "FERRET", "name": "Ferretería Industrial", "rfc": "FER234567KLM"},
        {"code": "IMPER", "name": "Impermeabilizantes PRO", "rfc": "IMP567890NOP"},
        {"code": "CIMEN", "name": "Cimentaciones Especiales", "rfc": "CIM890123QRS"},
    ]
    
    provider_ids = {}
    provider_codes = []
    for p in providers_data:
        provider = Provider(**p)
        provider_ids[p['code']] = provider.id
        provider_codes.append(p['code'])
        doc = provider.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.providers.insert_one(doc)
    
    # Create exchange rates for 3 months (Jan, Feb, Mar 2025)
    for month in [1, 2, 3]:
        for day in range(1, 29):
            date_str = f"2025-{month:02d}-{day:02d}"
            rate = 17.0 + (month * 0.15) + (day * 0.01) + random.uniform(-0.2, 0.2)
            exchange = ExchangeRate(date=date_str, rate=round(rate, 4))
            doc = exchange.model_dump()
            doc['created_at'] = doc['created_at'].isoformat()
            await db.exchange_rates.insert_one(doc)
    
    # Create budgets using partida_codigo from catalogo
    admin_user = await db.users.find_one({"role": "admin"}, {"_id": 0})
    admin_id = admin_user['id']
    
    # Budget amounts by partida codigo (using some key partidas)
    budget_partidas = ["104", "105", "106", "201", "205", "302"]  # EDIFICACION, URBANIZACION, etc.
    budget_amounts = {
        "104": 3000000,  # EDIFICACION
        "105": 800000,   # URBANIZACION
        "106": 500000,   # INDIRECTOS
        "201": 400000,   # PUBLICIDAD
        "205": 300000,   # GASTOS ADMIN
        "302": 200000,   # INTERESES
    }
    
    for proj_code, proj_id in project_ids.items():
        multiplier = 1.2 if proj_code == "TORRE-A" else 0.9
        for partida_codigo in budget_partidas:
            for month in [1, 2, 3]:
                amount = budget_amounts.get(partida_codigo, 500000) * multiplier
                budget = Budget(
                    project_id=proj_id,
                    partida_codigo=partida_codigo,
                    year=2025,
                    month=month,
                    amount_mxn=amount,
                    created_by=admin_id
                )
                doc = budget.model_dump()
                doc['created_at'] = doc['created_at'].isoformat()
                await db.budgets.insert_one(doc)
    
    finanzas_user = await db.users.find_one({"role": "finanzas"}, {"_id": 0})
    finanzas_id = finanzas_user['id']
    
    # Partida-Provider mapping for realistic data
    partida_provider_map = {
        "104": ["CEMEX", "ACERO", "CIMEN"],  # EDIFICACION
        "105": ["CEMEX", "TRANS", "FERRET"],  # URBANIZACION
        "106": ["SEGUV", "TRANS"],  # INDIRECTOS
        "201": ["PINTA", "VIDRI"],  # PUBLICIDAD
        "205": ["SEGUV", "TRANS"],  # GASTOS ADMIN
        "302": ["ELECT", "HIDRO"],  # INTERESES (placeholder)
    }
    
    partida_descriptions_map = {
        "104": ["Concreto premezclado", "Varilla corrugada", "Cimbra", "Block"],
        "105": ["Urbanización", "Pavimento", "Banquetas"],
        "106": ["Indirectos de obra", "Supervisión"],
        "201": ["Publicidad", "Promoción", "Materiales"],
        "205": ["Honorarios", "Licencias", "Permisos"],
        "302": ["Intereses bancarios", "Comisiones"],
    }
    
    # Generate exactly 200 movements
    movements_count = 0
    target_movements = 200
    project_list = list(project_ids.items())
    
    while movements_count < target_movements:
        proj_code, proj_id = random.choice(project_list)
        partida_codigo = random.choice(budget_partidas)
        month = random.choice([1, 2, 3])
        day = random.randint(1, 28)
        
        # Select provider
        available_providers = partida_provider_map.get(partida_codigo, provider_codes[:3])
        prov_code = random.choice(available_providers)
        prov_id = provider_ids.get(prov_code, provider_ids[provider_codes[0]])
        
        # Currency: 80% MXN, 20% USD
        currency = "USD" if random.random() < 0.2 else "MXN"
        
        if currency == "MXN":
            amount = random.randint(30000, 400000)
            exchange_rate = 1.0
        else:
            amount = random.randint(2000, 25000)
            date_str = f"2025-{month:02d}-{day:02d}"
            rate_doc = await db.exchange_rates.find_one({"date": date_str}, {"_id": 0})
            exchange_rate = rate_doc['rate'] if rate_doc else 17.5
        
        date_str = f"2025-{month:02d}-{day:02d}"
        description = random.choice(partida_descriptions_map.get(partida_codigo, ["Material"]))
        
        movement = Movement(
            project_id=proj_id,
            partida_codigo=partida_codigo,
            provider_id=prov_id,
            date=parse_date_tijuana(date_str),
            currency=Currency(currency),
            amount_original=amount,
            exchange_rate=exchange_rate,
            amount_mxn=amount * exchange_rate,
            reference=f"FAC-{random.randint(1000, 9999)}-{movements_count}",
            description=description,
            created_by=finanzas_id
        )
        doc = movement.model_dump()
        doc['date'] = doc['date'].isoformat()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.movements.insert_one(doc)
        movements_count += 1
    
    # Create some pending authorizations
    for i in range(3):
        auth = Authorization(
            movement_id=None,
            reason=f"Exceso de presupuesto en partida 104 EDIFICACION - {100 + i * 5}%",
            requested_by=finanzas_id
        )
        doc = auth.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.authorizations.insert_one(doc)
    
    # Log seed action
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": "system",
        "user_email": "system@finrealty.com",
        "user_role": "system",
        "action": "SEED",
        "entity": "database",
        "entity_id": "all",
        "changes": {"empresas": 3, "projects": 2, "catalogo_partidas": 29, "providers": 15, "movements": 200, "months": 3},
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    # Set default config
    configs = [
        {"key": "threshold_yellow", "value": 90},
        {"key": "threshold_red", "value": 100},
        {"key": "default_currency", "value": "MXN"},
        {"key": "timezone", "value": "America/Tijuana"},
    ]
    
    for c in configs:
        config = ConfigSetting(key=c['key'], value=c['value'], updated_by=admin_id)
        doc = config.model_dump()
        doc['updated_at'] = doc['updated_at'].isoformat()
        await db.config.insert_one(doc)
    
    return {
        "message": "Demo data seeded successfully",
        "data": {
            "users": 4,
            "projects": 2,
            "partidas": 6,
            "providers": 15,
            "movements": 200,
            "months": "Enero, Febrero, Marzo 2025"
        }
    }

# Include router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
