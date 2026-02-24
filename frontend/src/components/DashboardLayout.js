import { useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  LayoutDashboard,
  Wallet,
  ArrowRightLeft,
  CheckSquare,
  BarChart3,
  FolderOpen,
  ScrollText,
  Settings,
  Shield,
  LogOut,
  Menu,
  X,
  Bell,
  Users,
  Building2,
  ShoppingCart,
} from "lucide-react";
import { Button } from "./ui/button";
import { Avatar, AvatarFallback } from "./ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { Badge } from "./ui/badge";

const roleLabels = {
  admin: "Administrador",
  finanzas: "Finanzas",
  director: "Director",
  autorizador: "Autorizador",
  solo_lectura: "Solo Lectura",
  captura_ingresos: "Captura Ingresos"
};

const DashboardLayout = ({ children }) => {
  const { user, logout, hasRole, tokenClaims, allowedCompanies, selectCompany } = useAuth();
  const [selectedCompany, setSelectedCompany] = useState("");
  const [isSelectingCompany, setIsSelectingCompany] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const navItems = [
    { path: "/dashboard", icon: LayoutDashboard, label: "Dashboard", roles: ["admin", "finanzas", "autorizador", "solo_lectura", "captura_ingresos"] },
    { path: "/budgets", icon: Wallet, label: "Presupuestos", roles: ["admin", "finanzas"] },
    { path: "/movements", icon: ArrowRightLeft, label: "Movimientos", roles: ["admin", "finanzas", "captura_ingresos"] },
    { path: "/purchase-orders", icon: ShoppingCart, label: "Órdenes de Compra", roles: ["admin", "finanzas", "director"] },
    { path: "/authorizations", icon: CheckSquare, label: "Autorizaciones", roles: ["admin", "autorizador", "director"] },
    { path: "/reports", icon: BarChart3, label: "Reportes", roles: ["admin", "finanzas", "autorizador", "solo_lectura", "captura_ingresos", "director"] },
    { path: "/clientes", icon: Users, label: "Clientes", roles: ["admin", "finanzas", "captura_ingresos"] },
    { path: "/inventarios", icon: Building2, label: "Inventarios", roles: ["admin", "finanzas", "captura_ingresos"] },
    { path: "/catalogs", icon: FolderOpen, label: "Proveedores", roles: ["admin"] },
    { path: "/audit", icon: ScrollText, label: "Bitácora", roles: ["admin", "autorizador"] },
    { path: "/admin", icon: Shield, label: "Consola Admin", roles: ["admin"] },
    { path: "/settings", icon: Settings, label: "Mi Cuenta", roles: ["admin", "finanzas", "autorizador", "solo_lectura", "captura_ingresos", "director"] },
  ];

  const filteredNav = navItems.filter(item => 
    item.roles.some(role => hasRole(role))
  );



  const requiresCompanySelection = useMemo(() => {
    if (!user || user.role === "admin") return false;
    const selected = tokenClaims?.empresa_id || user?.empresa_id;
    return !selected;
  }, [user, tokenClaims]);

  const handleSelectCompany = async () => {
    if (!selectedCompany) return;
    try {
      setIsSelectingCompany(true);
      await selectCompany(selectedCompany);
      setSelectedCompany("");
    } finally {
      setIsSelectingCompany(false);
    }
  };

  const getInitials = (name) => {
    return name?.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2) || "??";
  };

  return (
    <div className="min-h-screen bg-background flex">
      {/* Sidebar */}
      <aside className={`fixed inset-y-0 left-0 z-50 w-64 bg-card border-r border-border transform transition-transform duration-200 lg:translate-x-0 ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="h-16 flex items-center px-6 border-b border-border">
            <img 
              src="/brand/quantum_logo.jpg" 
              alt="QFinance" 
              className="h-8 w-auto mr-3"
              data-testid="sidebar-logo"
            />
            <span className="font-heading text-xl font-bold tracking-tight">QFinance</span>
          </div>
          
          {/* Navigation */}
          <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
            {filteredNav.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  data-testid={`nav-${item.path.slice(1)}`}
                  className={`sidebar-link ${isActive ? "active" : ""}`}
                  onClick={() => setSidebarOpen(false)}
                >
                  <Icon className="h-5 w-5" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
          
          {/* User info */}
          <div className="p-4 border-t border-border">
            <div className="flex items-center gap-3">
              <Avatar className="h-9 w-9">
                <AvatarFallback className="bg-primary/20 text-primary text-sm">
                  {getInitials(user?.name)}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{user?.name}</p>
                <p className="text-xs text-muted-foreground truncate">{roleLabels[user?.role]}</p>
              </div>
            </div>
          </div>
        </div>
      </aside>
      
      {/* Overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      
      {/* Main content */}
      <div className="flex-1 lg:ml-64">
        {/* Top bar */}
        <header className="sticky top-0 z-30 h-16 bg-background/80 backdrop-blur-md border-b border-border">
          <div className="h-full px-4 flex items-center justify-between">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setSidebarOpen(true)}
              data-testid="mobile-menu-btn"
            >
              <Menu className="h-5 w-5" />
            </Button>
            
            <div className="flex-1" />
            
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" className="relative" data-testid="notifications-btn">
                <Bell className="h-5 w-5" />
              </Button>
              
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" className="gap-2" data-testid="user-menu-btn">
                    <Avatar className="h-8 w-8">
                      <AvatarFallback className="bg-primary/20 text-primary text-xs">
                        {getInitials(user?.name)}
                      </AvatarFallback>
                    </Avatar>
                    <span className="hidden md:inline text-sm">{user?.name}</span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <div className="px-2 py-1.5">
                    <p className="text-sm font-medium">{user?.name}</p>
                    <p className="text-xs text-muted-foreground">{user?.email}</p>
                  </div>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem>
                    <Badge variant="secondary" className="text-xs">{roleLabels[user?.role]}</Badge>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout} className="text-destructive" data-testid="logout-btn">
                    <LogOut className="h-4 w-4 mr-2" />
                    Cerrar sesión
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </header>
        
        {/* Page content */}
        <main className="p-6">
          {children}
        </main>

        {requiresCompanySelection && (
          <div className="fixed inset-0 z-[100] bg-black/50 flex items-center justify-center p-4">
            <div className="w-full max-w-md rounded-lg border border-border bg-card p-4 space-y-3">
              <h3 className="text-lg font-semibold">Selecciona empresa para operar</h3>
              {allowedCompanies.length === 0 ? (
                <p className="text-sm text-muted-foreground">No tienes empresas asignadas; contacta al administrador.</p>
              ) : (
                <>
                  <select
                    className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                    value={selectedCompany}
                    onChange={(e) => setSelectedCompany(e.target.value)}
                  >
                    <option value="">Selecciona empresa...</option>
                    {allowedCompanies.map((empresa) => (
                      <option key={empresa.id} value={empresa.id}>{empresa.nombre}</option>
                    ))}
                  </select>
                  <Button onClick={handleSelectCompany} disabled={!selectedCompany || isSelectingCompany}>
                    Continuar
                  </Button>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DashboardLayout;
