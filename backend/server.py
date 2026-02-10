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
    NORMAL = "normal"
    PENDING_AUTHORIZATION = "pending_authorization"
    AUTHORIZED = "authorized"
    REJECTED = "rejected"

# ========================= MODELS =========================
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
    description: Optional[str] = None
    is_active: bool = True

class Project(ProjectBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    partida_id: str
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
    partida_id: str
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
    status: MovementStatus = MovementStatus.NORMAL
    authorization_id: Optional[str] = None

class MovementCreate(BaseModel):
    project_id: str
    partida_id: str
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
    success_count: int
    error_count: int
    errors: List[Dict[str, Any]]
    movements_created: List[str]
    authorizations_required: List[str]

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
            raise HTTPException(status_code=403, detail="Permisos insuficientes")
        return current_user
    return role_checker

async def log_audit(user: dict, action: str, entity: str, entity_id: str, changes: dict):
    audit = AuditLog(
        user_id=user["user_id"],
        user_email=user["email"],
        user_role=user["role"],
        action=action,
        entity=entity,
        entity_id=entity_id,
        changes=changes
    )
    doc = audit.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.audit_logs.insert_one(doc)

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
    return TokenResponse(access_token=token, user=user)

@api_router.get("/auth/me", response_model=User)
async def get_me(current_user: dict = Depends(get_current_user)):
    user_doc = await db.users.find_one({"id": current_user["user_id"]}, {"_id": 0, "password_hash": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return User(**user_doc)

# ========================= USER ROUTES =========================
@api_router.get("/users", response_model=List[User])
async def get_users(current_user: dict = Depends(require_roles(UserRole.ADMIN))):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return [User(**u) for u in users]

@api_router.put("/users/{user_id}")
async def update_user(user_id: str, updates: dict, current_user: dict = Depends(require_roles(UserRole.ADMIN))):
    old_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not old_doc:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    allowed_fields = ["name", "role", "is_active"]
    update_data = {k: v for k, v in updates.items() if k in allowed_fields}
    
    await db.users.update_one({"id": user_id}, {"$set": update_data})
    await log_audit(current_user, "UPDATE", "users", user_id, {"before": old_doc, "after": update_data})
    return {"message": "Usuario actualizado"}

# ========================= PROJECT ROUTES =========================
@api_router.get("/projects", response_model=List[Project])
async def get_projects(current_user: dict = Depends(get_current_user)):
    projects = await db.projects.find({}, {"_id": 0}).to_list(1000)
    return [Project(**p) for p in projects]

@api_router.post("/projects", response_model=Project)
async def create_project(project_data: ProjectBase, current_user: dict = Depends(require_roles(UserRole.ADMIN))):
    project = Project(**project_data.model_dump())
    doc = project.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.projects.insert_one(doc)
    await log_audit(current_user, "CREATE", "projects", project.id, {"data": doc})
    return project

@api_router.put("/projects/{project_id}", response_model=Project)
async def update_project(project_id: str, updates: ProjectBase, current_user: dict = Depends(require_roles(UserRole.ADMIN))):
    old_doc = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not old_doc:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    
    update_data = updates.model_dump()
    await db.projects.update_one({"id": project_id}, {"$set": update_data})
    await log_audit(current_user, "UPDATE", "projects", project_id, {"before": old_doc, "after": update_data})
    
    updated = await db.projects.find_one({"id": project_id}, {"_id": 0})
    return Project(**updated)

# ========================= PARTIDA ROUTES =========================
@api_router.get("/partidas", response_model=List[Partida])
async def get_partidas(current_user: dict = Depends(get_current_user)):
    partidas = await db.partidas.find({}, {"_id": 0}).to_list(1000)
    return [Partida(**p) for p in partidas]

@api_router.post("/partidas", response_model=Partida)
async def create_partida(partida_data: PartidaBase, current_user: dict = Depends(require_roles(UserRole.ADMIN))):
    partida = Partida(**partida_data.model_dump())
    doc = partida.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.partidas.insert_one(doc)
    await log_audit(current_user, "CREATE", "partidas", partida.id, {"data": doc})
    return partida

@api_router.put("/partidas/{partida_id}", response_model=Partida)
async def update_partida(partida_id: str, updates: PartidaBase, current_user: dict = Depends(require_roles(UserRole.ADMIN))):
    old_doc = await db.partidas.find_one({"id": partida_id}, {"_id": 0})
    if not old_doc:
        raise HTTPException(status_code=404, detail="Partida no encontrada")
    
    update_data = updates.model_dump()
    await db.partidas.update_one({"id": partida_id}, {"$set": update_data})
    await log_audit(current_user, "UPDATE", "partidas", partida_id, {"before": old_doc, "after": update_data})
    
    updated = await db.partidas.find_one({"id": partida_id}, {"_id": 0})
    return Partida(**updated)

# ========================= PROVIDER ROUTES =========================
@api_router.get("/providers", response_model=List[Provider])
async def get_providers(current_user: dict = Depends(get_current_user)):
    providers = await db.providers.find({}, {"_id": 0}).to_list(1000)
    return [Provider(**p) for p in providers]

@api_router.post("/providers", response_model=Provider)
async def create_provider(provider_data: ProviderBase, current_user: dict = Depends(require_roles(UserRole.ADMIN))):
    provider = Provider(**provider_data.model_dump())
    doc = provider.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.providers.insert_one(doc)
    await log_audit(current_user, "CREATE", "providers", provider.id, {"data": doc})
    return provider

@api_router.put("/providers/{provider_id}", response_model=Provider)
async def update_provider(provider_id: str, updates: ProviderBase, current_user: dict = Depends(require_roles(UserRole.ADMIN))):
    old_doc = await db.providers.find_one({"id": provider_id}, {"_id": 0})
    if not old_doc:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    
    update_data = updates.model_dump()
    await db.providers.update_one({"id": provider_id}, {"$set": update_data})
    await log_audit(current_user, "UPDATE", "providers", provider_id, {"before": old_doc, "after": update_data})
    
    updated = await db.providers.find_one({"id": provider_id}, {"_id": 0})
    return Provider(**updated)

# ========================= BUDGET ROUTES =========================
@api_router.get("/budgets", response_model=List[Budget])
async def get_budgets(
    project_id: Optional[str] = None,
    partida_id: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {}
    if project_id:
        query["project_id"] = project_id
    if partida_id:
        query["partida_id"] = partida_id
    if year:
        query["year"] = year
    if month:
        query["month"] = month
    
    budgets = await db.budgets.find(query, {"_id": 0}).to_list(1000)
    return [Budget(**b) for b in budgets]

@api_router.post("/budgets", response_model=Budget)
async def create_budget(budget_data: BudgetBase, current_user: dict = Depends(require_roles(UserRole.ADMIN, UserRole.FINANZAS))):
    existing = await db.budgets.find_one({
        "project_id": budget_data.project_id,
        "partida_id": budget_data.partida_id,
        "year": budget_data.year,
        "month": budget_data.month
    }, {"_id": 0})
    
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe presupuesto para este proyecto/partida/mes")
    
    budget = Budget(**budget_data.model_dump(), created_by=current_user["user_id"])
    doc = budget.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.budgets.insert_one(doc)
    await log_audit(current_user, "CREATE", "budgets", budget.id, {"data": doc})
    return budget

@api_router.put("/budgets/{budget_id}", response_model=Budget)
async def update_budget(budget_id: str, updates: BudgetBase, current_user: dict = Depends(require_roles(UserRole.ADMIN, UserRole.FINANZAS))):
    old_doc = await db.budgets.find_one({"id": budget_id}, {"_id": 0})
    if not old_doc:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    
    update_data = updates.model_dump()
    await db.budgets.update_one({"id": budget_id}, {"$set": update_data})
    await log_audit(current_user, "UPDATE", "budgets", budget_id, {"before": old_doc, "after": update_data})
    
    updated = await db.budgets.find_one({"id": budget_id}, {"_id": 0})
    return Budget(**updated)

@api_router.delete("/budgets/{budget_id}")
async def delete_budget(budget_id: str, current_user: dict = Depends(require_roles(UserRole.ADMIN))):
    old_doc = await db.budgets.find_one({"id": budget_id}, {"_id": 0})
    if not old_doc:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado")
    
    await db.budgets.delete_one({"id": budget_id})
    await log_audit(current_user, "DELETE", "budgets", budget_id, {"deleted": old_doc})
    return {"message": "Presupuesto eliminado"}

# ========================= EXCHANGE RATE ROUTES =========================
@api_router.get("/exchange-rates")
async def get_exchange_rates(current_user: dict = Depends(get_current_user)):
    rates = await db.exchange_rates.find({}, {"_id": 0}).to_list(1000)
    return rates

@api_router.post("/exchange-rates")
async def create_exchange_rate(date_str: str, rate: float, current_user: dict = Depends(require_roles(UserRole.ADMIN, UserRole.FINANZAS))):
    existing = await db.exchange_rates.find_one({"date": date_str}, {"_id": 0})
    if existing:
        await db.exchange_rates.update_one({"date": date_str}, {"$set": {"rate": rate}})
        return {"message": "Tipo de cambio actualizado"}
    
    exchange = ExchangeRate(date=date_str, rate=rate)
    doc = exchange.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.exchange_rates.insert_one(doc)
    return {"message": "Tipo de cambio creado"}

# ========================= MOVEMENT ROUTES =========================
@api_router.get("/movements")
async def get_movements(
    project_id: Optional[str] = None,
    partida_id: Optional[str] = None,
    provider_id: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {}
    if project_id:
        query["project_id"] = project_id
    if partida_id:
        query["partida_id"] = partida_id
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
async def create_movement(movement_data: MovementCreate, current_user: dict = Depends(require_roles(UserRole.ADMIN, UserRole.FINANZAS))):
    # Validate references
    project = await db.projects.find_one({"id": movement_data.project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=400, detail="Proyecto no válido")
    
    partida = await db.partidas.find_one({"id": movement_data.partida_id}, {"_id": 0})
    if not partida:
        raise HTTPException(status_code=400, detail="Partida no válida")
    
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
        "partida_id": movement_data.partida_id,
        "year": year,
        "month": month
    }, {"_id": 0})
    
    # Calculate current spent
    current_movements = await db.movements.find({
        "project_id": movement_data.project_id,
        "partida_id": movement_data.partida_id,
        "status": {"$in": ["normal", "authorized"]}
    }, {"_id": 0}).to_list(5000)
    
    current_spent = sum(
        m['amount_mxn'] for m in current_movements
        if date_parser.parse(m['date']).year == year and date_parser.parse(m['date']).month == month
    )
    
    budget_amount = budget['amount_mxn'] if budget else 0
    new_total = current_spent + amount_mxn
    
    # Determine if authorization required
    requires_auth = False
    auth_reason = ""
    
    if budget_amount == 0:
        requires_auth = True
        auth_reason = "Presupuesto no definido ($0)"
    elif (new_total / budget_amount) > 1.0:
        requires_auth = True
        auth_reason = f"Exceso de presupuesto: {(new_total / budget_amount * 100):.1f}%"
    
    movement = Movement(
        project_id=movement_data.project_id,
        partida_id=movement_data.partida_id,
        provider_id=movement_data.provider_id,
        date=parsed_date,
        currency=movement_data.currency,
        amount_original=movement_data.amount_original,
        exchange_rate=movement_data.exchange_rate,
        amount_mxn=amount_mxn,
        reference=movement_data.reference,
        description=movement_data.description,
        created_by=current_user["user_id"],
        status=MovementStatus.PENDING_AUTHORIZATION if requires_auth else MovementStatus.NORMAL
    )
    
    doc = movement.model_dump()
    doc['date'] = doc['date'].isoformat()
    doc['created_at'] = doc['created_at'].isoformat()
    
    # Create authorization if needed
    if requires_auth:
        auth = Authorization(
            movement_id=movement.id,
            reason=auth_reason,
            requested_by=current_user["user_id"]
        )
        auth_doc = auth.model_dump()
        auth_doc['created_at'] = auth_doc['created_at'].isoformat()
        await db.authorizations.insert_one(auth_doc)
        doc['authorization_id'] = auth.id
    
    await db.movements.insert_one(doc)
    await log_audit(current_user, "CREATE", "movements", movement.id, {"data": doc, "requires_auth": requires_auth})
    
    return {"movement": doc, "requires_authorization": requires_auth, "reason": auth_reason if requires_auth else None}

@api_router.post("/movements/import")
async def import_movements(file: UploadFile = File(...), current_user: dict = Depends(require_roles(UserRole.ADMIN, UserRole.FINANZAS))):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos CSV")
    
    content = await file.read()
    decoded = content.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(decoded))
    
    results = CSVImportResult(
        success_count=0,
        error_count=0,
        errors=[],
        movements_created=[],
        authorizations_required=[]
    )
    
    # Get lookups
    projects = {p['code']: p for p in await db.projects.find({}, {"_id": 0}).to_list(1000)}
    partidas = {p['code']: p for p in await db.partidas.find({}, {"_id": 0}).to_list(1000)}
    providers = {p['code']: p for p in await db.providers.find({}, {"_id": 0}).to_list(1000)}
    exchange_rates = {r['date']: r['rate'] for r in await db.exchange_rates.find({}, {"_id": 0}).to_list(1000)}
    
    row_num = 1
    for row in reader:
        row_num += 1
        errors = []
        
        # Validate required fields
        required = ['fecha', 'proyecto', 'partida', 'proveedor', 'moneda', 'monto', 'referencia']
        for field in required:
            if field not in row or not row[field].strip():
                errors.append(f"Campo '{field}' requerido")
        
        if errors:
            results.errors.append({"row": row_num, "errors": errors})
            results.error_count += 1
            continue
        
        # Validate project
        project = projects.get(row['proyecto'].strip())
        if not project:
            errors.append(f"Proyecto '{row['proyecto']}' no encontrado")
        
        # Validate partida
        partida = partidas.get(row['partida'].strip())
        if not partida:
            errors.append(f"Partida '{row['partida']}' no encontrada")
        
        # Validate provider
        provider = providers.get(row['proveedor'].strip())
        if not provider:
            errors.append(f"Proveedor '{row['proveedor']}' no encontrado")
        
        # Validate currency
        currency = row['moneda'].strip().upper()
        if currency not in ['MXN', 'USD']:
            errors.append(f"Moneda '{currency}' no válida (MXN/USD)")
        
        # Validate amount
        try:
            amount = float(row['monto'].replace(',', '').strip())
            if amount <= 0:
                errors.append("Monto debe ser mayor a 0")
        except ValueError:
            errors.append(f"Monto '{row['monto']}' no es válido")
            amount = 0
        
        # Validate date
        try:
            parsed_date = parse_date_tijuana(row['fecha'].strip())
            date_key = parsed_date.strftime('%Y-%m-%d')
        except Exception:
            errors.append(f"Fecha '{row['fecha']}' no válida")
            parsed_date = None
            date_key = None
        
        # Get exchange rate
        exchange_rate = 1.0
        if currency == 'USD':
            if date_key and date_key in exchange_rates:
                exchange_rate = exchange_rates[date_key]
            else:
                errors.append(f"Tipo de cambio no encontrado para {date_key}")
        
        if errors:
            results.errors.append({"row": row_num, "errors": errors})
            results.error_count += 1
            continue
        
        # Check duplicates
        dup_check = await db.movements.find_one({
            "date": parsed_date.isoformat(),
            "provider_id": provider['id'],
            "amount_original": amount,
            "reference": row['referencia'].strip()
        }, {"_id": 0})
        
        if dup_check:
            results.errors.append({"row": row_num, "errors": ["Movimiento duplicado"]})
            results.error_count += 1
            continue
        
        # Calculate amount in MXN
        amount_mxn = amount * exchange_rate
        
        # Check budget
        year = parsed_date.year
        month = parsed_date.month
        
        budget = await db.budgets.find_one({
            "project_id": project['id'],
            "partida_id": partida['id'],
            "year": year,
            "month": month
        }, {"_id": 0})
        
        current_movements = await db.movements.find({
            "project_id": project['id'],
            "partida_id": partida['id'],
            "status": {"$in": ["normal", "authorized"]}
        }, {"_id": 0}).to_list(5000)
        
        current_spent = sum(
            m['amount_mxn'] for m in current_movements
            if date_parser.parse(m['date']).year == year and date_parser.parse(m['date']).month == month
        )
        
        budget_amount = budget['amount_mxn'] if budget else 0
        new_total = current_spent + amount_mxn
        
        requires_auth = False
        auth_reason = ""
        
        if budget_amount == 0:
            requires_auth = True
            auth_reason = "Presupuesto no definido ($0)"
        elif (new_total / budget_amount) > 1.0:
            requires_auth = True
            auth_reason = f"Exceso de presupuesto: {(new_total / budget_amount * 100):.1f}%"
        
        # Create movement
        movement = Movement(
            project_id=project['id'],
            partida_id=partida['id'],
            provider_id=provider['id'],
            date=parsed_date,
            currency=Currency(currency),
            amount_original=amount,
            exchange_rate=exchange_rate,
            amount_mxn=amount_mxn,
            reference=row['referencia'].strip(),
            description=row.get('descripcion', '').strip() if row.get('descripcion') else None,
            created_by=current_user["user_id"],
            status=MovementStatus.PENDING_AUTHORIZATION if requires_auth else MovementStatus.NORMAL
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
            await db.authorizations.insert_one(auth_doc)
            doc['authorization_id'] = auth.id
            results.authorizations_required.append(movement.id)
        
        await db.movements.insert_one(doc)
        results.movements_created.append(movement.id)
        results.success_count += 1
    
    await log_audit(current_user, "IMPORT", "movements", "batch", {
        "success": results.success_count,
        "errors": results.error_count
    })
    
    return results

# ========================= AUTHORIZATION ROUTES =========================
@api_router.get("/authorizations")
async def get_authorizations(
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {}
    if status:
        query["status"] = status
    
    auths = await db.authorizations.find(query, {"_id": 0}).to_list(1000)
    return auths

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
    
    update_data = {
        "status": resolution.status.value,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "resolved_by": current_user["user_id"],
        "notes": resolution.notes
    }
    
    await db.authorizations.update_one({"id": auth_id}, {"$set": update_data})
    
    # Update movement status
    if auth.get('movement_id'):
        new_status = MovementStatus.AUTHORIZED if resolution.status == AuthorizationStatus.APPROVED else MovementStatus.REJECTED
        await db.movements.update_one(
            {"id": auth['movement_id']},
            {"$set": {"status": new_status.value}}
        )
    
    await log_audit(current_user, "RESOLVE", "authorizations", auth_id, {
        "resolution": resolution.status.value,
        "notes": resolution.notes
    })
    
    return {"message": f"Autorización {resolution.status.value}"}

# ========================= REPORTS ROUTES =========================
@api_router.get("/reports/dashboard")
async def get_dashboard(
    project_id: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    now = to_tijuana(datetime.now(timezone.utc))
    year = year or now.year
    month = month or now.month
    
    # Get budgets
    budget_query = {"year": year, "month": month}
    if project_id:
        budget_query["project_id"] = project_id
    
    budgets = await db.budgets.find(budget_query, {"_id": 0}).to_list(1000)
    
    # Get movements
    movement_query = {"status": {"$in": ["normal", "authorized"]}}
    if project_id:
        movement_query["project_id"] = project_id
    
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
        key = b['partida_id']
        if key not in partidas_data:
            partidas_data[key] = {"budget": 0, "real": 0}
        partidas_data[key]["budget"] += b['amount_mxn']
    
    for m in movements:
        key = m['partida_id']
        if key not in partidas_data:
            partidas_data[key] = {"budget": 0, "real": 0}
        partidas_data[key]["real"] += m['amount_mxn']
    
    # Get partida names
    partida_docs = await db.partidas.find({}, {"_id": 0}).to_list(1000)
    partida_map = {p['id']: p for p in partida_docs}
    
    partidas_summary = []
    for partida_id, data in partidas_data.items():
        pct = (data['real'] / data['budget'] * 100) if data['budget'] > 0 else (100 if data['real'] > 0 else 0)
        partida_info = partida_map.get(partida_id, {})
        partidas_summary.append({
            "partida_id": partida_id,
            "partida_code": partida_info.get('code', 'N/A'),
            "partida_name": partida_info.get('name', 'N/A'),
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
    
    # Pending authorizations count
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
        "by_partida": sorted(partidas_summary, key=lambda x: x['percentage'], reverse=True),
        "by_project": sorted(projects_summary, key=lambda x: x['percentage'], reverse=True),
        "pending_authorizations": pending_auths,
        "movements_count": len(movements)
    }

@api_router.get("/reports/partida-detail/{partida_id}")
async def get_partida_detail(
    partida_id: str,
    project_id: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    now = to_tijuana(datetime.now(timezone.utc))
    year = year or now.year
    month = month or now.month
    
    # Get partida
    partida = await db.partidas.find_one({"id": partida_id}, {"_id": 0})
    if not partida:
        raise HTTPException(status_code=404, detail="Partida no encontrada")
    
    # Get budgets
    budget_query = {"partida_id": partida_id, "year": year, "month": month}
    if project_id:
        budget_query["project_id"] = project_id
    
    budgets = await db.budgets.find(budget_query, {"_id": 0}).to_list(1000)
    total_budget = sum(b['amount_mxn'] for b in budgets)
    
    # Get movements
    movement_query = {"partida_id": partida_id, "status": {"$in": ["normal", "authorized"]}}
    if project_id:
        movement_query["project_id"] = project_id
    
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
        "partida": partida,
        "year": year,
        "month": month,
        "budget": total_budget,
        "real": total_real,
        "variation": total_budget - total_real,
        "percentage": percentage,
        "traffic_light": get_traffic_light(percentage),
        "movements": sorted(movements, key=lambda x: x['date'], reverse=True)
    }

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

# ========================= DEMO DATA =========================
@api_router.post("/seed-demo-data")
async def seed_demo_data():
    """Seed demo data: 2 proyectos, 6 partidas, 15 proveedores, 200 movimientos, 3 meses"""
    import random
    
    # Clear existing data
    await db.users.delete_many({})
    await db.projects.delete_many({})
    await db.partidas.delete_many({})
    await db.providers.delete_many({})
    await db.budgets.delete_many({})
    await db.movements.delete_many({})
    await db.authorizations.delete_many({})
    await db.exchange_rates.delete_many({})
    await db.audit_logs.delete_many({})
    await db.config.delete_many({})
    
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
    
    # Create 2 projects
    projects_data = [
        {"code": "TORRE-A", "name": "Torre Altavista", "description": "Desarrollo residencial premium 25 pisos"},
        {"code": "PLAZA-M", "name": "Plaza Comercial Marina", "description": "Centro comercial frente al mar"},
    ]
    
    project_ids = {}
    for p in projects_data:
        project = Project(**p)
        project_ids[p['code']] = project.id
        doc = project.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.projects.insert_one(doc)
    
    # Create 6 partidas
    partidas_data = [
        {"code": "CONST", "name": "Construcción", "description": "Obra civil y estructura"},
        {"code": "ELEC", "name": "Instalaciones Eléctricas", "description": "Sistema eléctrico completo"},
        {"code": "HIDRA", "name": "Instalaciones Hidráulicas", "description": "Sistema hidráulico y sanitario"},
        {"code": "ACAB", "name": "Acabados", "description": "Pisos, pintura, carpintería"},
        {"code": "ADMIN", "name": "Gastos Administrativos", "description": "Permisos, licencias, honorarios"},
        {"code": "EQUIP", "name": "Equipamiento", "description": "Elevadores, aire acondicionado"},
    ]
    
    partida_ids = {}
    for p in partidas_data:
        partida = Partida(**p)
        partida_ids[p['code']] = partida.id
        doc = partida.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.partidas.insert_one(doc)
    
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
    
    # Create budgets for 2 projects x 6 partidas x 3 months
    admin_user = await db.users.find_one({"role": "admin"}, {"_id": 0})
    admin_id = admin_user['id']
    
    budget_amounts = {
        "CONST": 2500000,
        "ELEC": 600000,
        "HIDRA": 400000,
        "ACAB": 750000,
        "ADMIN": 250000,
        "EQUIP": 1000000,
    }
    
    for proj_code, proj_id in project_ids.items():
        multiplier = 1.2 if proj_code == "TORRE-A" else 0.9
        for part_code, part_id in partida_ids.items():
            for month in [1, 2, 3]:
                amount = budget_amounts[part_code] * multiplier
                budget = Budget(
                    project_id=proj_id,
                    partida_id=part_id,
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
    
    movement_templates = [
        {"partida": "CONST", "provider": "CEMEX", "desc": "Concreto premezclado"},
        {"partida": "CONST", "provider": "ACERO", "desc": "Varilla corrugada"},
        {"partida": "ELEC", "provider": "ELECT", "desc": "Material eléctrico"},
        {"partida": "HIDRA", "provider": "HIDRO", "desc": "Tubería y conexiones"},
        {"partida": "ACAB", "provider": "PINTA", "desc": "Pintura vinílica"},
        {"partida": "EQUIP", "provider": "ELEVA", "desc": "Anticipo elevadores"},
    ]
    
    for proj_code, proj_id in project_ids.items():
        for month in range(1, 4):  # First 3 months with movements
            for _ in range(random.randint(5, 10)):
                template = random.choice(movement_templates)
                day = random.randint(1, 28)
                
                currency = random.choice(["MXN", "MXN", "MXN", "USD"])
                amount = random.randint(50000, 500000) if currency == "MXN" else random.randint(3000, 30000)
                
                date_str = f"2025-{month:02d}-{day:02d}"
                exchange_rate = 1.0 if currency == "MXN" else 17.0 + (month * 0.1)
                
                movement = Movement(
                    project_id=proj_id,
                    partida_id=partida_ids[template["partida"]],
                    provider_id=provider_ids[template["provider"]],
                    date=parse_date_tijuana(date_str),
                    currency=Currency(currency),
                    amount_original=amount,
                    exchange_rate=exchange_rate,
                    amount_mxn=amount * exchange_rate,
                    reference=f"FAC-{random.randint(1000, 9999)}",
                    description=template["desc"],
                    created_by=finanzas_id
                )
                doc = movement.model_dump()
                doc['date'] = doc['date'].isoformat()
                doc['created_at'] = doc['created_at'].isoformat()
                await db.movements.insert_one(doc)
    
    # Create some pending authorizations
    for i in range(3):
        auth = Authorization(
            movement_id=None,
            reason=f"Exceso de presupuesto en partida CONST - {100 + i * 5}%",
            requested_by=finanzas_id
        )
        doc = auth.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.authorizations.insert_one(doc)
    
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
    
    return {"message": "Demo data seeded successfully", "users": len(users_data), "projects": len(projects_data)}

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
