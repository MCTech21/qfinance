import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { Lock, Mail, Loader2 } from "lucide-react";
import axios from "axios";

const API_URL = process.env.REACT_APP_BACKEND_URL;

const Login = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSeeding, setIsSeeding] = useState(false);
  const { login, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) {
      navigate("/dashboard");
    }
  }, [user, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    
    try {
      await login(email, password);
      toast.success("Bienvenido al sistema");
      navigate("/dashboard");
    } catch (error) {
      const message = error.response?.data?.detail || "Error al iniciar sesión";
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSeedData = async () => {
    setIsSeeding(true);
    try {
      await axios.post(`${API_URL}/api/seed-demo-data`);
      toast.success("Datos demo cargados correctamente");
    } catch (error) {
      toast.error("Error al cargar datos demo");
    } finally {
      setIsSeeding(false);
    }
  };

  const demoUsers = [
    { email: "admin@finrealty.com", password: "admin123", role: "Administrador" },
    { email: "finanzas@finrealty.com", password: "finanzas123", role: "Finanzas" },
    { email: "autorizador@finrealty.com", password: "auth123", role: "Autorizador" },
    { email: "lectura@finrealty.com", password: "lectura123", role: "Solo Lectura" },
  ];

  return (
    <div className="min-h-screen bg-background flex">
      {/* Left side - Image */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/20 to-transparent z-10" />
        <img
          src="https://images.unsplash.com/photo-1651666176094-2bef8442db12?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjY2NzF8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBvZmZpY2UlMjBidWlsZGluZyUyMGFyY2hpdGVjdHVyZXxlbnwwfHx8fDE3NzA3NjQ0Mzl8MA&ixlib=rb-4.1.0&q=85"
          alt="Building"
          className="object-cover w-full h-full"
        />
        {/* Logo overlay on image */}
        <div className="absolute top-6 left-6 z-20">
          <img 
            src="/brand/quantum_logo.jpg" 
            alt="QFinance" 
            className="h-12 w-auto"
            data-testid="login-logo-overlay"
          />
        </div>
        <div className="absolute bottom-0 left-0 right-0 p-8 bg-gradient-to-t from-black/80 to-transparent z-20">
          <h1 className="font-heading text-4xl font-bold text-white mb-2">QFinance</h1>
          <p className="text-white/80 text-lg">Sistema de Control Financiero para Desarrollos Inmobiliarios</p>
        </div>
      </div>
      
      {/* Right side - Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md space-y-8 animate-in">
          {/* Logo for mobile */}
          <div className="lg:hidden text-center mb-8">
            <div className="inline-flex items-center gap-3 mb-4">
              <img 
                src="/brand/quantum_logo.jpg" 
                alt="QFinance" 
                className="h-10 w-auto"
                data-testid="login-logo-mobile"
              />
              <span className="font-heading text-3xl font-bold">QFinance</span>
            </div>
          </div>
          
          <div className="space-y-2 text-center lg:text-left">
            <h2 className="font-heading text-3xl font-bold tracking-tight">Iniciar Sesión</h2>
            <p className="text-muted-foreground">Ingresa tus credenciales para acceder al sistema</p>
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="email">Correo electrónico</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="email"
                  type="email"
                  placeholder="correo@empresa.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-10"
                  required
                  data-testid="login-email"
                />
              </div>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="password">Contraseña</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-10"
                  required
                  data-testid="login-password"
                />
              </div>
            </div>
            
            <Button
              type="submit"
              className="w-full"
              disabled={isLoading}
              data-testid="login-submit"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Iniciando...
                </>
              ) : (
                "Iniciar Sesión"
              )}
            </Button>
          </form>
          
          {/* Demo section */}
          <div className="pt-6 border-t border-border">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm text-muted-foreground">Usuarios demo:</span>
              <Button
                variant="outline"
                size="sm"
                onClick={handleSeedData}
                disabled={isSeeding}
                data-testid="seed-data-btn"
              >
                {isSeeding ? (
                  <>
                    <Loader2 className="h-3 w-3 mr-2 animate-spin" />
                    Cargando...
                  </>
                ) : (
                  "Cargar datos demo"
                )}
              </Button>
            </div>
            
            <div className="grid grid-cols-2 gap-2">
              {demoUsers.map((demo) => (
                <button
                  key={demo.email}
                  type="button"
                  onClick={() => {
                    setEmail(demo.email);
                    setPassword(demo.password);
                  }}
                  className="text-left p-3 rounded-md border border-border hover:bg-muted/50 transition-colors"
                  data-testid={`demo-user-${demo.role.toLowerCase().replace(/\s+/g, '-')}`}
                >
                  <p className="text-xs font-medium truncate">{demo.email}</p>
                  <p className="text-xs text-muted-foreground">{demo.role}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
