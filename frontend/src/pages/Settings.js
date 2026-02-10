import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Settings2, Loader2, Save } from "lucide-react";

const Settings = () => {
  const { api } = useAuth();
  const [config, setConfig] = useState({
    threshold_yellow: 90,
    threshold_red: 100,
    default_currency: "MXN",
    timezone: "America/Tijuana"
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await api().get("/config");
      setConfig(prev => ({ ...prev, ...response.data }));
    } catch (error) {
      toast.error("Error al cargar configuración");
    } finally {
      setIsLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSave = async (key, value) => {
    setIsSaving(true);
    try {
      await api().put(`/config/${key}`, value, {
        headers: { "Content-Type": "application/json" }
      });
      toast.success("Configuración guardada");
    } catch (error) {
      toast.error("Error al guardar");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveAll = async () => {
    setIsSaving(true);
    try {
      await Promise.all([
        api().put("/config/threshold_yellow", config.threshold_yellow, { headers: { "Content-Type": "application/json" } }),
        api().put("/config/threshold_red", config.threshold_red, { headers: { "Content-Type": "application/json" } })
      ]);
      toast.success("Configuración guardada");
    } catch (error) {
      toast.error("Error al guardar");
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="settings-page">
      <div>
        <h1 className="font-heading text-3xl font-bold tracking-tight">Configuración</h1>
        <p className="text-muted-foreground">Ajustes generales del sistema</p>
      </div>

      <div className="grid gap-6 max-w-2xl">
        {/* Traffic Light Thresholds */}
        <Card>
          <CardHeader>
            <CardTitle className="font-heading text-lg flex items-center gap-2">
              <Settings2 className="h-5 w-5" />
              Umbrales del Semáforo
            </CardTitle>
            <CardDescription>
              Configura los porcentajes para el sistema de semáforo presupuestal
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <Label>Umbral Amarillo (%)</Label>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-amber-500" />
                  <Input
                    type="number"
                    value={config.threshold_yellow}
                    onChange={(e) => setConfig(prev => ({ ...prev, threshold_yellow: Number(e.target.value) }))}
                    min="0"
                    max="100"
                    data-testid="threshold-yellow-input"
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  Alerta cuando el gasto supera este % del presupuesto
                </p>
              </div>
              
              <div className="space-y-2">
                <Label>Umbral Rojo (%)</Label>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500" />
                  <Input
                    type="number"
                    value={config.threshold_red}
                    onChange={(e) => setConfig(prev => ({ ...prev, threshold_red: Number(e.target.value) }))}
                    min="0"
                    max="200"
                    data-testid="threshold-red-input"
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  Exceso cuando el gasto supera este % del presupuesto
                </p>
              </div>
            </div>
            
            <div className="p-4 bg-muted rounded-lg">
              <h4 className="font-medium mb-2">Vista previa:</h4>
              <div className="flex gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-emerald-500" />
                  <span>Verde: 0% - {config.threshold_yellow}%</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-amber-500" />
                  <span>Amarillo: {config.threshold_yellow}% - {config.threshold_red}%</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500" />
                  <span>Rojo: {">"}{config.threshold_red}%</span>
                </div>
              </div>
            </div>
            
            <Button onClick={handleSaveAll} disabled={isSaving} data-testid="save-settings-btn">
              {isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
              Guardar Cambios
            </Button>
          </CardContent>
        </Card>

        {/* System Info */}
        <Card>
          <CardHeader>
            <CardTitle className="font-heading text-lg">Información del Sistema</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between py-2 border-b border-border">
                <span className="text-muted-foreground">Zona horaria</span>
                <span className="font-mono">{config.timezone}</span>
              </div>
              <div className="flex justify-between py-2 border-b border-border">
                <span className="text-muted-foreground">Moneda predeterminada</span>
                <span className="font-mono">{config.default_currency}</span>
              </div>
              <div className="flex justify-between py-2 border-b border-border">
                <span className="text-muted-foreground">Versión</span>
                <span className="font-mono">1.0.0</span>
              </div>
              <div className="flex justify-between py-2">
                <span className="text-muted-foreground">Ambiente</span>
                <span className="font-mono">Demo</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Settings;
