import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Settings2, Loader2, Save, KeyRound } from "lucide-react";

const Settings = () => {
  const { api, user, changePassword, logout } = useAuth();
  const [config, setConfig] = useState({
    threshold_yellow: 90,
    threshold_red: 100,
    default_currency: "MXN",
    timezone: "America/Tijuana",
  });
  const [pwd, setPwd] = useState({ current: "", next: "", confirm: "" });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const isAdmin = user?.role === "admin";

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      if (isAdmin) {
        const response = await api().get("/config");
        setConfig((prev) => ({ ...prev, ...response.data }));
      }
    } catch {
      toast.error("Error al cargar configuración");
    } finally {
      setIsLoading(false);
    }
  }, [api, isAdmin]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSaveAll = async () => {
    setIsSaving(true);
    try {
      await Promise.all([
        api().put("/config/threshold_yellow", config.threshold_yellow, { headers: { "Content-Type": "application/json" } }),
        api().put("/config/threshold_red", config.threshold_red, { headers: { "Content-Type": "application/json" } }),
      ]);
      toast.success("Configuración guardada");
    } catch {
      toast.error("Error al guardar");
    } finally {
      setIsSaving(false);
    }
  };

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    if (pwd.next !== pwd.confirm) {
      toast.error("La confirmación de contraseña no coincide");
      return;
    }
    if (pwd.current === pwd.next) {
      toast.error("La nueva contraseña debe ser diferente a la actual");
      return;
    }
    setIsSaving(true);
    try {
      await changePassword(pwd.current, pwd.next);
      toast.success("Contraseña actualizada");
      setPwd({ current: "", next: "", confirm: "" });
      logout();
      toast.info("Vuelve a iniciar sesión con tu nueva contraseña");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al cambiar contraseña");
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <div className="flex justify-center py-8"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>;
  }

  return (
    <div className="space-y-6" data-testid="settings-page">
      <div>
        <h1 className="font-heading text-3xl font-bold tracking-tight">Mi cuenta</h1>
        <p className="text-muted-foreground">Configuración personal y seguridad</p>
      </div>

      <div className="grid gap-6 max-w-2xl">
        <Card>
          <CardHeader>
            <CardTitle className="font-heading text-lg flex items-center gap-2"><KeyRound className="h-5 w-5" />Cambiar contraseña</CardTitle>
            <CardDescription>Actualiza tu contraseña de acceso.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handlePasswordChange} className="space-y-4">
              <div className="space-y-2"><Label>Contraseña actual</Label><Input type="password" value={pwd.current} onChange={(e) => setPwd((p) => ({ ...p, current: e.target.value }))} required /></div>
              <div className="space-y-2"><Label>Nueva contraseña</Label><Input type="password" value={pwd.next} onChange={(e) => setPwd((p) => ({ ...p, next: e.target.value }))} required minLength={8} /></div>
              <div className="space-y-2"><Label>Confirmar nueva contraseña</Label><Input type="password" value={pwd.confirm} onChange={(e) => setPwd((p) => ({ ...p, confirm: e.target.value }))} required minLength={8} /></div>
              <Button type="submit" disabled={isSaving} data-testid="change-password-btn">{isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}Cambiar contraseña</Button>
            </form>
          </CardContent>
        </Card>

        {isAdmin && (
          <Card>
            <CardHeader>
              <CardTitle className="font-heading text-lg flex items-center gap-2"><Settings2 className="h-5 w-5" />Umbrales del Semáforo</CardTitle>
              <CardDescription>Configura los porcentajes para el sistema de semáforo presupuestal</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-2"><Label>Umbral Amarillo (%)</Label><Input type="number" value={config.threshold_yellow} onChange={(e) => setConfig((p) => ({ ...p, threshold_yellow: Number(e.target.value) }))} min="0" max="100" /></div>
                <div className="space-y-2"><Label>Umbral Rojo (%)</Label><Input type="number" value={config.threshold_red} onChange={(e) => setConfig((p) => ({ ...p, threshold_red: Number(e.target.value) }))} min="0" max="200" /></div>
              </div>
              <Button onClick={handleSaveAll} disabled={isSaving} data-testid="save-settings-btn">{isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}Guardar Cambios</Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default Settings;
