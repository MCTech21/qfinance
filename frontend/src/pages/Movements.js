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
import { Plus, Upload, Loader2, FileSpreadsheet, AlertCircle, CheckCircle, Pencil, Trash2 } from "lucide-react";
import { buildYearOptions } from "../lib/yearRange";

const Movements = () => {
  const { api, user } = useAuth();
  const [movements, setMovements] = useState([]);
  const [empresas, setEmpresas] = useState([]);
  const [projects, setProjects] = useState([]);
  const [filteredProjects, setFilteredProjects] = useState([]);
  const [catalogoPartidas, setCatalogoPartidas] = useState([]);
  const [providers, setProviders] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const fileInputRef = useRef(null);
  
  const [filters, setFilters] = useState({
    empresa_id: "all",
    project_id: "all",
    partida_codigo: "all",
    year: new Date().getFullYear(),
    month: new Date().getMonth() + 1
  });
  
  const [formData, setFormData] = useState({
    project_id: "",
    partida_codigo: "",
    provider_id: "",
    date: new Date().toISOString().split("T")[0],
    currency: "MXN",
    amount_original: "",
    exchange_rate: "1",
    reference: "",
    description: ""
  });

  const yearOptions = buildYearOptions();
  const captureAllowedCodes = ["103", "203", "206", "402", "403"];
  const isCaptureUser = user?.role === "captura" || user?.role === "captura_ingresos";
  const isIngresoNoProvider = ["402", "403"].includes(String(formData.partida_codigo || ""));
  const isAdmin = user?.role === "admin";
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedMovement, setSelectedMovement] = useState(null);
  const [editFormData, setEditFormData] = useState({});
  const [editReason, setEditReason] = useState("");
  const [deleteReason, setDeleteReason] = useState("");
  const [deleteMode, setDeleteMode] = useState("soft");
  const [hardDeleteConfirmText, setHardDeleteConfirmText] = useState("");
  const [isEditSaving, setIsEditSaving] = useState(false);
  const [isDeleteSaving, setIsDeleteSaving] = useState(false);

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
      const [movementsRes, empresasRes, projectsRes, partidasRes, providersRes] = await Promise.all([
        api().get("/movements", {
          params: {
            project_id: filters.project_id !== "all" ? filters.project_id : undefined,
            partida_codigo: filters.partida_codigo !== "all" ? filters.partida_codigo : undefined,
            year: filters.year,
            month: filters.month
          }
        }),
        api().get("/empresas"),
        api().get("/projects"),
        api().get("/catalogo-partidas"),
        api().get("/providers")
      ]);
      setMovements(movementsRes.data);
      setEmpresas(empresasRes.data);
      setProjects(projectsRes.data);
      setCatalogoPartidas(partidasRes.data);
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

  // Filter projects by empresa
  useEffect(() => {
    if (filters.empresa_id === "all") {
      setFilteredProjects(projects);
    } else {
      setFilteredProjects(projects.filter(p => p.empresa_id === filters.empresa_id));
    }
  }, [filters.empresa_id, projects]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    
    try {
      const payload = {
        ...formData,
        amount_original: parseFloat(formData.amount_original),
        exchange_rate: parseFloat(formData.exchange_rate),
        provider_id: isIngresoNoProvider ? null : formData.provider_id,
        customer_name: isIngresoNoProvider ? String(formData.customer_name || "").trim() : undefined,
      };

      if (isIngresoNoProvider && !payload.customer_name) {
        toast.error("Nombre del cliente es obligatorio para partidas 402/403");
        setIsSaving(false);
        return;
      }
      
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
      partida_codigo: "",
      provider_id: "",
      customer_name: "",
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
  const getPartidaNombre = (codigo) => {
    const p = catalogoPartidas.find(p => p.codigo === codigo);
    return p ? `${p.codigo} - ${p.nombre}` : codigo;
  };
  const getProviderName = (id) => providers.find(p => p.id === id)?.name || "N/A";

  const handleApiError = (error, fallbackMessage) => {
    const status = error?.response?.status;
    const detail = error?.response?.data?.detail;
    if (status === 403) {
      toast.error("No autorizado");
      return;
    }
    if (status === 409) {
      toast.error(typeof detail === "string" ? detail : "Conflicto al procesar la solicitud");
      return;
    }
    if (status === 422) {
      if (Array.isArray(detail)) {
        toast.error(detail.map((item) => item?.msg).filter(Boolean).join(" | "));
      } else {
        toast.error(typeof detail === "string" ? detail : "Datos inválidos");
      }
      return;
    }
    toast.error(typeof detail === "string" ? detail : fallbackMessage);
  };

  const openEditDialog = (movement) => {
    setSelectedMovement(movement);
    const dateValue = movement?.date ? new Date(movement.date).toISOString().split("T")[0] : "";
    setEditFormData({
      project_id: movement?.project_id || "",
      partida_codigo: movement?.partida_codigo || "",
      provider_id: movement?.provider_id || "",
      customer_name: movement?.customer_name || "",
      date: dateValue,
      currency: movement?.currency || "MXN",
      amount_original: String(movement?.amount_original ?? ""),
      exchange_rate: String(movement?.exchange_rate ?? "1"),
      reference: movement?.reference || "",
      description: movement?.description || "",
    });
    setEditReason("");
    setEditDialogOpen(true);
  };

  const openDeleteDialog = (movement) => {
    setSelectedMovement(movement);
    setDeleteReason("");
    setDeleteMode("soft");
    setHardDeleteConfirmText("");
    setDeleteDialogOpen(true);
  };

  const isEditIngresoNoProvider = ["402", "403"].includes(String(editFormData.partida_codigo || ""));

  const handleEditMovement = async (e) => {
    e.preventDefault();
    if (!editReason.trim()) {
      toast.error("El motivo es obligatorio");
      return;
    }

    const payload = {
      ...editFormData,
      amount_original: parseFloat(editFormData.amount_original),
      exchange_rate: parseFloat(editFormData.exchange_rate),
      provider_id: isEditIngresoNoProvider ? null : editFormData.provider_id,
      customer_name: isEditIngresoNoProvider ? String(editFormData.customer_name || "").trim() : undefined,
      reason: editReason.trim(),
    };

    if (isEditIngresoNoProvider && !payload.customer_name) {
      toast.error("Nombre del cliente es obligatorio para partidas 402/403");
      return;
    }

    setIsEditSaving(true);
    try {
      await api().patch(`/movements/${selectedMovement.id}`, payload);
      toast.success("Actualizado");
      setEditDialogOpen(false);
      setSelectedMovement(null);
      fetchData();
    } catch (error) {
      handleApiError(error, "Error al actualizar movimiento");
    } finally {
      setIsEditSaving(false);
    }
  };

  const canConfirmHardDelete = hardDeleteConfirmText === "HARD-DELETE-MOVEMENT" && deleteReason.trim().length > 0;
  const canConfirmSoftDelete = deleteReason.trim().length > 0;

  const handleDeleteMovement = async () => {
    if (!selectedMovement) return;
    if (!deleteReason.trim()) {
      toast.error("El motivo es obligatorio");
      return;
    }
    if (deleteMode === "hard" && !canConfirmHardDelete) {
      toast.error("Debes confirmar exactamente HARD-DELETE-MOVEMENT");
      return;
    }

    setIsDeleteSaving(true);
    try {
      if (deleteMode === "hard") {
        await api().delete(`/movements/${selectedMovement.id}/hard`, {
          data: { reason: deleteReason.trim() },
          headers: { "X-Confirm-Hard-Delete": "HARD-DELETE-MOVEMENT" }
        });
      } else {
        await api().delete(`/movements/${selectedMovement.id}`, {
          data: { reason: deleteReason.trim() }
        });
      }
      toast.success(deleteMode === "hard" ? "Movimiento eliminado (hard delete)" : "Movimiento eliminado");
      setDeleteDialogOpen(false);
      setSelectedMovement(null);
      fetchData();
    } catch (error) {
      handleApiError(error, "Error al eliminar movimiento");
    } finally {
      setIsDeleteSaving(false);
    }
  };

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
                    <li>• proyecto: código del proyecto (ej: TORRE-A)</li>
                    <li>• partida: código del catálogo (100-404)</li>
                    <li>• proveedor: código del proveedor</li>
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
            <DialogContent className="max-w-xl">
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
                    <Label>Partida (Catálogo)</Label>
                    <Select
                      value={formData.partida_codigo}
                      onValueChange={(v) => setFormData(prev => ({ ...prev, partida_codigo: v }))}
                    >
                      <SelectTrigger data-testid="movement-partida-select">
                        <SelectValue placeholder="Seleccionar partida..." />
                      </SelectTrigger>
                      <SelectContent className="max-h-[300px]">
                        {catalogoPartidas.filter((p) => !isCaptureUser || captureAllowedCodes.includes(String(p.codigo))).map(p => (
                          <SelectItem key={p.codigo} value={p.codigo}>
                            {p.codigo} - {p.nombre}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                
                {isIngresoNoProvider ? (
                  <div className="space-y-2">
                    <Label>Cliente</Label>
                    <Input
                      value={formData.customer_name || ""}
                      onChange={(e) => setFormData(prev => ({ ...prev, customer_name: e.target.value }))}
                      placeholder="Nombre del cliente"
                      required
                      minLength={2}
                      data-testid="movement-customer-name-input"
                    />
                  </div>
                ) : (
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
                )}
                
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

          <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
            <DialogContent className="max-w-xl">
              <DialogHeader>
                <DialogTitle>Editar Movimiento</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleEditMovement} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Proyecto</Label>
                    <Select value={editFormData.project_id || ""} onValueChange={(v) => setEditFormData(prev => ({ ...prev, project_id: v }))}>
                      <SelectTrigger><SelectValue placeholder="Seleccionar..." /></SelectTrigger>
                      <SelectContent>
                        {projects.map(p => (<SelectItem key={p.id} value={p.id}>{p.code} - {p.name}</SelectItem>))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Partida (Catálogo)</Label>
                    <Select value={editFormData.partida_codigo || ""} onValueChange={(v) => setEditFormData(prev => ({ ...prev, partida_codigo: v }))}>
                      <SelectTrigger><SelectValue placeholder="Seleccionar partida..." /></SelectTrigger>
                      <SelectContent className="max-h-[300px]">
                        {catalogoPartidas.map(p => (<SelectItem key={p.codigo} value={p.codigo}>{p.codigo} - {p.nombre}</SelectItem>))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {isEditIngresoNoProvider ? (
                  <div className="space-y-2">
                    <Label>Cliente</Label>
                    <Input value={editFormData.customer_name || ""} onChange={(e) => setEditFormData(prev => ({ ...prev, customer_name: e.target.value }))} placeholder="Nombre del cliente" required />
                  </div>
                ) : (
                  <div className="space-y-2">
                    <Label>Proveedor</Label>
                    <Select value={editFormData.provider_id || ""} onValueChange={(v) => setEditFormData(prev => ({ ...prev, provider_id: v }))}>
                      <SelectTrigger><SelectValue placeholder="Seleccionar..." /></SelectTrigger>
                      <SelectContent>
                        {providers.map(p => (<SelectItem key={p.id} value={p.id}>{p.code} - {p.name}</SelectItem>))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Fecha</Label>
                    <Input type="date" value={editFormData.date || ""} onChange={(e) => setEditFormData(prev => ({ ...prev, date: e.target.value }))} required />
                  </div>
                  <div className="space-y-2">
                    <Label>Referencia</Label>
                    <Input value={editFormData.reference || ""} onChange={(e) => setEditFormData(prev => ({ ...prev, reference: e.target.value }))} required />
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label>Moneda</Label>
                    <Select value={editFormData.currency || "MXN"} onValueChange={(v) => setEditFormData(prev => ({ ...prev, currency: v, exchange_rate: v === "MXN" ? "1" : prev.exchange_rate }))}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="MXN">MXN</SelectItem>
                        <SelectItem value="USD">USD</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Monto</Label>
                    <Input type="number" min="0.01" step="0.01" value={editFormData.amount_original || ""} onChange={(e) => setEditFormData(prev => ({ ...prev, amount_original: e.target.value }))} required />
                  </div>
                  <div className="space-y-2">
                    <Label>Tipo Cambio</Label>
                    <Input type="number" min="0.01" step="0.0001" value={editFormData.exchange_rate || "1"} onChange={(e) => setEditFormData(prev => ({ ...prev, exchange_rate: e.target.value }))} disabled={editFormData.currency === "MXN"} />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Descripción</Label>
                  <Input value={editFormData.description || ""} onChange={(e) => setEditFormData(prev => ({ ...prev, description: e.target.value }))} placeholder="Descripción del movimiento..." />
                </div>

                <div className="space-y-2">
                  <Label>Motivo</Label>
                  <Input value={editReason} onChange={(e) => setEditReason(e.target.value)} placeholder="Motivo de la edición" required data-testid="movement-edit-reason-input" />
                </div>

                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setEditDialogOpen(false)} disabled={isEditSaving}>Cancelar</Button>
                  <Button type="submit" disabled={isEditSaving || !editReason.trim()} data-testid="movement-edit-submit-btn">
                    {isEditSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                    Guardar
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>

          <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>Eliminar Movimiento</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Tipo de eliminación</Label>
                  <div className="flex gap-2">
                    <Button type="button" variant={deleteMode === "soft" ? "default" : "outline"} onClick={() => setDeleteMode("soft")}>Soft delete (recomendado)</Button>
                    <Button type="button" variant={deleteMode === "hard" ? "destructive" : "outline"} onClick={() => setDeleteMode("hard")}>Hard delete (peligroso)</Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Motivo</Label>
                  <Input value={deleteReason} onChange={(e) => setDeleteReason(e.target.value)} placeholder="Motivo de la eliminación" required data-testid="movement-delete-reason-input" />
                </div>

                {deleteMode === "hard" && (
                  <div className="space-y-2">
                    <Label>Confirmación hard delete</Label>
                    <Input value={hardDeleteConfirmText} onChange={(e) => setHardDeleteConfirmText(e.target.value)} placeholder="Escribe HARD-DELETE-MOVEMENT" data-testid="movement-hard-delete-confirm-input" />
                  </div>
                )}

                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setDeleteDialogOpen(false)} disabled={isDeleteSaving}>Cancelar</Button>
                  <Button
                    type="button"
                    variant={deleteMode === "hard" ? "destructive" : "default"}
                    onClick={handleDeleteMovement}
                    disabled={isDeleteSaving || (deleteMode === "hard" ? !canConfirmHardDelete : !canConfirmSoftDelete)}
                    data-testid="movement-delete-confirm-btn"
                  >
                    {isDeleteSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                    Confirmar
                  </Button>
                </DialogFooter>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-4">
            <Select
              value={filters.empresa_id}
              onValueChange={(v) => setFilters(prev => ({ ...prev, empresa_id: v, project_id: "all" }))}
            >
              <SelectTrigger className="w-[180px]" data-testid="filter-empresa">
                <SelectValue placeholder="Empresa" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas</SelectItem>
                {empresas.map(e => (
                  <SelectItem key={e.id} value={e.id}>{e.nombre}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            <Select
              value={filters.project_id}
              onValueChange={(v) => setFilters(prev => ({ ...prev, project_id: v }))}
            >
              <SelectTrigger className="w-[180px]" data-testid="filter-project">
                <SelectValue placeholder="Proyecto" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                {filteredProjects.map(p => (
                  <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            <Select
              value={filters.partida_codigo}
              onValueChange={(v) => setFilters(prev => ({ ...prev, partida_codigo: v }))}
            >
              <SelectTrigger className="w-[220px]">
                <SelectValue placeholder="Partida" />
              </SelectTrigger>
              <SelectContent className="max-h-[300px]">
                <SelectItem value="all">Todas las partidas</SelectItem>
                {catalogoPartidas.filter((p) => !isCaptureUser || captureAllowedCodes.includes(String(p.codigo))).map(p => (
                  <SelectItem key={p.codigo} value={p.codigo}>{p.codigo} - {p.nombre}</SelectItem>
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
                {yearOptions.map(y => (
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
                    {isAdmin && <th>Acciones</th>}
                  </tr>
                </thead>
                <tbody>
                  {movements.map(mov => (
                    <tr key={mov.id}>
                      <td className="font-mono text-sm">{formatDate(mov.date)}</td>
                      <td>{getProjectName(mov.project_id)}</td>
                      <td className="text-sm">{mov.partida_codigo}</td>
                      <td className="max-w-[220px] truncate">{mov.provider_id ? getProviderName(mov.provider_id) : (mov.customer_name ? `Cliente: ${mov.customer_name}` : "N/A")}</td>
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
                      {isAdmin && (
                        <td>
                          <div className="flex gap-2">
                            <Button size="sm" variant="outline" onClick={() => openEditDialog(mov)} data-testid={`movement-edit-btn-${mov.id}`}>
                              <Pencil className="h-3 w-3 mr-1" />
                              Editar
                            </Button>
                            <Button size="sm" variant="destructive" onClick={() => openDeleteDialog(mov)} data-testid={`movement-delete-btn-${mov.id}`}>
                              <Trash2 className="h-3 w-3 mr-1" />
                              Eliminar
                            </Button>
                          </div>
                        </td>
                      )}
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
