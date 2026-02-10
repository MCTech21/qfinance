import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import { Badge } from "../components/ui/badge";
import TrafficLight from "../components/TrafficLight";
import { Plus, Upload, Loader2, FileSpreadsheet, AlertCircle, CheckCircle } from "lucide-react";

const Movements = () => {
  const { api } = useAuth();
  const [movements, setMovements] = useState([]);
  const [projects, setProjects] = useState([]);
  const [partidas, setPartidas] = useState([]);
  const [providers, setProviders] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const fileInputRef = useRef(null);
  
  const [filters, setFilters] = useState({
    project_id: "all",
    partida_id: "all",
    year: new Date().getFullYear(),
    month: new Date().getMonth() + 1
  });
  
  const [formData, setFormData] = useState({
    project_id: "",
    partida_id: "",
    provider_id: "",
    date: new Date().toISOString().split("T")[0],
    currency: "MXN",
    amount_original: "",
    exchange_rate: "1",
    reference: "",
    description: ""
  });

  const months = [
    { value: 1, label: "Enero" }, { value: 2, label: "Febrero" }, { value: 3, label: "Marzo" },
    { value: 4, label: "Abril" }, { value: 5, label: "Mayo" }, { value: 6, label: "Junio" },
    { value: 7, label: "Julio" }, { value: 8, label: "Agosto" }, { value: 9, label: "Septiembre" },
    { value: 10, label: "Octubre" }, { value: 11, label: "Noviembre" }, { value: 12, label: "Diciembre" },
  ];

  const statusLabels = {
    normal: { label: "Normal", variant: "secondary" },
    pending_authorization: { label: "Pendiente", variant: "outline" },
    authorized: { label: "Autorizado", variant: "default" },
    rejected: { label: "Rechazado", variant: "destructive" }
  };

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [movementsRes, projectsRes, partidasRes, providersRes] = await Promise.all([
        api().get("/movements", {
          params: {
            project_id: filters.project_id !== "all" ? filters.project_id : undefined,
            partida_id: filters.partida_id !== "all" ? filters.partida_id : undefined,
            year: filters.year,
            month: filters.month
          }
        }),
        api().get("/projects"),
        api().get("/partidas"),
        api().get("/providers")
      ]);
      setMovements(movementsRes.data);
      setProjects(projectsRes.data);
      setPartidas(partidasRes.data);
      setProviders(providersRes.data);
    } catch (error) {
      toast.error("Error al cargar movimientos");
    } finally {
      setIsLoading(false);
    }
  }, [api, filters]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    
    try {
      const payload = {
        ...formData,
        amount_original: parseFloat(formData.amount_original),
        exchange_rate: parseFloat(formData.exchange_rate)
      };
      
      const response = await api().post("/movements", payload);
      
      if (response.data.requires_authorization) {
        toast.warning(`Movimiento creado - Requiere autorización: ${response.data.reason}`);
      } else {
        toast.success("Movimiento creado correctamente");
      }
      
      setDialogOpen(false);
      fetchData();
      resetForm();
    } catch (error) {
      const message = error.response?.data?.detail || "Error al crear movimiento";
      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleImport = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setIsSaving(true);
    setImportResult(null);
    
    try {
      const formData = new FormData();
      formData.append("file", file);
      
      const response = await api().post("/movements/import", formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      
      setImportResult(response.data);
      
      if (response.data.error_count === 0) {
        toast.success(`${response.data.success_count} movimientos importados`);
      } else {
        toast.warning(`${response.data.success_count} importados, ${response.data.error_count} errores`);
      }
      
      fetchData();
    } catch (error) {
      toast.error("Error al importar archivo");
    } finally {
      setIsSaving(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const resetForm = () => {
    setFormData({
      project_id: "",
      partida_id: "",
      provider_id: "",
      date: new Date().toISOString().split("T")[0],
      currency: "MXN",
      amount_original: "",
      exchange_rate: "1",
      reference: "",
      description: ""
    });
  };

  const formatCurrency = (num, currency = "MXN") => {
    return new Intl.NumberFormat("es-MX", {
      style: "currency",
      currency: currency,
      minimumFractionDigits: 2,
    }).format(num);
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString("es-MX", {
      day: "2-digit",
      month: "short",
      year: "numeric"
    });
  };

  const getProjectName = (id) => projects.find(p => p.id === id)?.code || "N/A";
  const getPartidaCode = (id) => partidas.find(p => p.id === id)?.code || "N/A";
  const getProviderName = (id) => providers.find(p => p.id === id)?.name || "N/A";

  return (
    <div className="space-y-6" data-testid="movements-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight">Movimientos</h1>
          <p className="text-muted-foreground">Registro de movimientos financieros</p>
        </div>
        
        <div className="flex gap-2">
          <Dialog open={importDialogOpen} onOpenChange={setImportDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" data-testid="import-movements-btn">
                <Upload className="h-4 w-4 mr-2" />
                Importar CSV
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Importar Movimientos desde CSV</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div className="p-4 bg-muted rounded-lg">
                  <h4 className="font-medium mb-2">Formato requerido del CSV:</h4>
                  <code className="text-xs block bg-background p-2 rounded">
                    fecha,proyecto,partida,proveedor,moneda,monto,referencia,descripcion
                  </code>
                  <ul className="text-xs text-muted-foreground mt-2 space-y-1">
                    <li>• fecha: YYYY-MM-DD</li>
                    <li>• proyecto/partida/proveedor: usar códigos del catálogo</li>
                    <li>• moneda: MXN o USD</li>
                    <li>• monto: número positivo</li>
                  </ul>
                </div>
                
                <div className="flex items-center gap-4">
                  <Input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv"
                    onChange={handleImport}
                    disabled={isSaving}
                    data-testid="csv-file-input"
                  />
                  {isSaving && <Loader2 className="h-5 w-5 animate-spin" />}
                </div>
                
                {importResult && (
                  <div className="space-y-3">
                    <div className="flex gap-4">
                      <div className="flex items-center gap-2 text-emerald-400">
                        <CheckCircle className="h-4 w-4" />
                        <span>{importResult.success_count} exitosos</span>
                      </div>
                      <div className="flex items-center gap-2 text-red-400">
                        <AlertCircle className="h-4 w-4" />
                        <span>{importResult.error_count} errores</span>
                      </div>
                    </div>
                    
                    {importResult.authorizations_required.length > 0 && (
                      <div className="text-amber-400 text-sm">
                        {importResult.authorizations_required.length} movimientos requieren autorización
                      </div>
                    )}
                    
                    {importResult.errors.length > 0 && (
                      <div className="max-h-40 overflow-y-auto">
                        {importResult.errors.map((err, idx) => (
                          <div key={idx} className="text-xs text-red-400 py-1 border-b border-border">
                            Fila {err.row}: {err.errors.join(", ")}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </DialogContent>
          </Dialog>
          
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button data-testid="add-movement-btn">
                <Plus className="h-4 w-4 mr-2" />
                Nuevo Movimiento
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Nuevo Movimiento</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Proyecto</Label>
                    <Select
                      value={formData.project_id}
                      onValueChange={(v) => setFormData(prev => ({ ...prev, project_id: v }))}
                    >
                      <SelectTrigger data-testid="movement-project-select">
                        <SelectValue placeholder="Seleccionar..." />
                      </SelectTrigger>
                      <SelectContent>
                        {projects.map(p => (
                          <SelectItem key={p.id} value={p.id}>{p.code} - {p.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Partida</Label>
                    <Select
                      value={formData.partida_id}
                      onValueChange={(v) => setFormData(prev => ({ ...prev, partida_id: v }))}
                    >
                      <SelectTrigger data-testid="movement-partida-select">
                        <SelectValue placeholder="Seleccionar..." />
                      </SelectTrigger>
                      <SelectContent>
                        {partidas.map(p => (
                          <SelectItem key={p.id} value={p.id}>{p.code} - {p.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label>Proveedor</Label>
                  <Select
                    value={formData.provider_id}
                    onValueChange={(v) => setFormData(prev => ({ ...prev, provider_id: v }))}
                  >
                    <SelectTrigger data-testid="movement-provider-select">
                      <SelectValue placeholder="Seleccionar..." />
                    </SelectTrigger>
                    <SelectContent>
                      {providers.map(p => (
                        <SelectItem key={p.id} value={p.id}>{p.code} - {p.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Fecha</Label>
                    <Input
                      type="date"
                      value={formData.date}
                      onChange={(e) => setFormData(prev => ({ ...prev, date: e.target.value }))}
                      required
                      data-testid="movement-date-input"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Referencia</Label>
                    <Input
                      value={formData.reference}
                      onChange={(e) => setFormData(prev => ({ ...prev, reference: e.target.value }))}
                      placeholder="FAC-001, OC-123..."
                      required
                      data-testid="movement-reference-input"
                    />
                  </div>
                </div>
                
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label>Moneda</Label>
                    <Select
                      value={formData.currency}
                      onValueChange={(v) => setFormData(prev => ({ 
                        ...prev, 
                        currency: v,
                        exchange_rate: v === "MXN" ? "1" : prev.exchange_rate
                      }))}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="MXN">MXN</SelectItem>
                        <SelectItem value="USD">USD</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Monto</Label>
                    <Input
                      type="number"
                      value={formData.amount_original}
                      onChange={(e) => setFormData(prev => ({ ...prev, amount_original: e.target.value }))}
                      placeholder="0.00"
                      min="0.01"
                      step="0.01"
                      required
                      data-testid="movement-amount-input"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Tipo Cambio</Label>
                    <Input
                      type="number"
                      value={formData.exchange_rate}
                      onChange={(e) => setFormData(prev => ({ ...prev, exchange_rate: e.target.value }))}
                      min="0.01"
                      step="0.0001"
                      disabled={formData.currency === "MXN"}
                      data-testid="movement-exchange-rate-input"
                    />
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label>Descripción</Label>
                  <Input
                    value={formData.description}
                    onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Descripción del movimiento..."
                  />
                </div>
                
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                    Cancelar
                  </Button>
                  <Button type="submit" disabled={isSaving} data-testid="movement-submit-btn">
                    {isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                    Crear
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-4">
            <Select
              value={filters.project_id}
              onValueChange={(v) => setFilters(prev => ({ ...prev, project_id: v }))}
            >
              <SelectTrigger className="w-[180px]" data-testid="filter-project">
                <SelectValue placeholder="Proyecto" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                {projects.map(p => (
                  <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            <Select
              value={filters.partida_id}
              onValueChange={(v) => setFilters(prev => ({ ...prev, partida_id: v }))}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Partida" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas</SelectItem>
                {partidas.map(p => (
                  <SelectItem key={p.id} value={p.id}>{p.code} - {p.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            <Select
              value={String(filters.month)}
              onValueChange={(v) => setFilters(prev => ({ ...prev, month: Number(v) }))}
            >
              <SelectTrigger className="w-[140px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {months.map(m => (
                  <SelectItem key={m.value} value={String(m.value)}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            <Select
              value={String(filters.year)}
              onValueChange={(v) => setFilters(prev => ({ ...prev, year: Number(v) }))}
            >
              <SelectTrigger className="w-[100px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[2024, 2025, 2026].map(y => (
                  <SelectItem key={y} value={String(y)}>{y}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle className="font-heading text-lg flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5" />
            Lista de Movimientos ({movements.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : movements.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No hay movimientos para el período seleccionado
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table" data-testid="movements-table">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Proyecto</th>
                    <th>Partida</th>
                    <th>Proveedor</th>
                    <th>Referencia</th>
                    <th className="text-right">Monto Original</th>
                    <th className="text-right">Monto MXN</th>
                    <th>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {movements.map(mov => (
                    <tr key={mov.id}>
                      <td className="font-mono text-sm">{formatDate(mov.date)}</td>
                      <td>{getProjectName(mov.project_id)}</td>
                      <td>{getPartidaCode(mov.partida_id)}</td>
                      <td className="max-w-[150px] truncate">{getProviderName(mov.provider_id)}</td>
                      <td className="font-mono text-sm">{mov.reference}</td>
                      <td className="mono-number">
                        {formatCurrency(mov.amount_original, mov.currency)}
                        {mov.currency === "USD" && (
                          <span className="text-xs text-muted-foreground ml-1">USD</span>
                        )}
                      </td>
                      <td className="mono-number">{formatCurrency(mov.amount_mxn)}</td>
                      <td>
                        <Badge variant={statusLabels[mov.status]?.variant || "secondary"}>
                          {statusLabels[mov.status]?.label || mov.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default Movements;
