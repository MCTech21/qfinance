import { buildYearOptions } from "../lib/yearRange";
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { CheckCircle, XCircle, Clock, Loader2, AlertTriangle, TrendingUp, DollarSign, FileText } from "lucide-react";
import TrafficLight from "../components/TrafficLight";

const Authorizations = () => {
  const { api, user } = useAuth();
  const [authorizations, setAuthorizations] = useState([]);
  const [empresas, setEmpresas] = useState([]);
  const [projects, setProjects] = useState([]);
  const [filteredProjects, setFilteredProjects] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [resolving, setResolving] = useState(null);
  const [notes, setNotes] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedAuth, setSelectedAuth] = useState(null);
  const [action, setAction] = useState(null);
  
  const [filters, setFilters] = useState({
    empresa_id: "all",
    project_id: "all",
    year: new Date().getFullYear(),
    month: new Date().getMonth() + 1,
    status: "pending"
  });
  const [partialAmount, setPartialAmount] = useState("");
  const [resolveError, setResolveError] = useState("");

  const yearOptions = buildYearOptions();

  const months = [
    { value: 1, label: "Enero" }, { value: 2, label: "Febrero" }, { value: 3, label: "Marzo" },
    { value: 4, label: "Abril" }, { value: 5, label: "Mayo" }, { value: 6, label: "Junio" },
    { value: 7, label: "Julio" }, { value: 8, label: "Agosto" }, { value: 9, label: "Septiembre" },
    { value: 10, label: "Octubre" }, { value: 11, label: "Noviembre" }, { value: 12, label: "Diciembre" },
  ];

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = {
        status: filters.status !== "all" ? filters.status : undefined,
        empresa_id: filters.empresa_id !== "all" ? filters.empresa_id : undefined,
        project_id: filters.project_id !== "all" ? filters.project_id : undefined,
        year: filters.year,
        month: filters.month
      };
      
      const [authRes, empresasRes, projectsRes] = await Promise.all([
        api().get("/authorizations", { params }),
        api().get("/empresas"),
        api().get("/projects")
      ]);
      
      setAuthorizations(authRes.data);
      setEmpresas(empresasRes.data);
      setProjects(projectsRes.data);
    } catch (error) {
      toast.error("Error al cargar autorizaciones");
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


  const toNumber = (value) => {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
  };

  const getApiMessage = (error, fallback = "Error al procesar autorización") => {
    const detail = error?.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (detail?.message) return detail.message;
    if (detail?.code) return detail.code;
    return fallback;
  };

  const selectedSummary = selectedAuth?.budget_gate_summary || selectedAuth?.budget_preview || null;
  const selectedPo = selectedAuth?.purchase_order_details || null;
  const pendingAmount = toNumber(selectedPo?.pending_amount ?? selectedSummary?.monto_pendiente_oc ?? selectedPo?.totals?.total ?? 0);
  const approvedAccumulated = toNumber(selectedPo?.approved_amount_total ?? selectedSummary?.monto_aprobado_acumulado ?? 0);
  const totalOc = toNumber(selectedPo?.totals?.total ?? selectedSummary?.monto_oc ?? selectedAuth?.movement_details?.monto_mxn ?? 0);
  const requestedApproval = action === "approved" && partialAmount !== "" ? toNumber(partialAmount) : pendingAmount;
  const projectedRemainingIfPartial = toNumber(selectedSummary?.disponible_actual ?? 0) - requestedApproval;

  const handleResolve = async () => {
    if (!selectedAuth || !action) return;
    
    // Reject requires notes
    if (action === "rejected" && !notes.trim()) {
      toast.error("El rechazo requiere un motivo");
      return;
    }
    
    setResolving(selectedAuth.id);
    setResolveError("");
    try {
      await api().put(`/authorizations/${selectedAuth.id}`, {
        status: action,
        notes: notes,
        partial_amount: action === "approved" && partialAmount !== "" ? Number(partialAmount) : undefined,
      });

      toast.success(action === "approved" ? "Autorización resuelta correctamente" : "Movimiento rechazado");
      setDialogOpen(false);
      setSelectedAuth(null);
      setNotes("");
      setPartialAmount("");
      fetchData();
    } catch (error) {
      const msg = getApiMessage(error);
      setResolveError(msg);
      toast.error(msg);
    } finally {
      setResolving(null);
    }
  };

  const openResolveDialog = (auth, actionType) => {
    setSelectedAuth(auth);
    setAction(actionType);
    setNotes("");
    setPartialAmount("");
    setResolveError("");
    setDialogOpen(true);
  };

  const formatCurrency = (num) => {
    return new Intl.NumberFormat("es-MX", {
      style: "currency",
      currency: "MXN",
      minimumFractionDigits: 0,
    }).format(num || 0);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "-";
    const d = new Date(dateStr);
    if (Number.isNaN(d.getTime())) return "-";
    return d.toLocaleString("es-MX", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  const pendingAuths = authorizations.filter(a => a.status === "pending");
  const resolvedAuths = authorizations.filter(a => a.status !== "pending");

  const statusConfig = {
    pending: { icon: Clock, color: "text-amber-400", bg: "bg-amber-500/10", label: "Pendiente" },
    approved: { icon: CheckCircle, color: "text-emerald-400", bg: "bg-emerald-500/10", label: "Aprobado" },
    rejected: { icon: XCircle, color: "text-red-400", bg: "bg-red-500/10", label: "Rechazado" }
  };

  const canResolve = user?.role === "admin" || user?.role === "autorizador" || user?.role === "director";

  return (
    <div className="space-y-6" data-testid="authorizations-page">
      <div>
        <h1 className="font-heading text-3xl font-bold tracking-tight">Autorizaciones</h1>
        <p className="text-muted-foreground">Gestión de autorizaciones para excesos de presupuesto (&gt;100%) y pendientes</p>
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
                <SelectItem value="all">Todas las empresas</SelectItem>
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
                  <SelectItem key={p.id} value={p.id}>{p.code} - {p.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            <Select
              value={String(filters.month)}
              onValueChange={(v) => setFilters(prev => ({ ...prev, month: Number(v) }))}
            >
              <SelectTrigger className="w-[130px]">
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
            
            <Select
              value={filters.status}
              onValueChange={(v) => setFilters(prev => ({ ...prev, status: v }))}
            >
              <SelectTrigger className="w-[140px]" data-testid="filter-status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="pending">Pendientes</SelectItem>
                <SelectItem value="approved">Aprobados</SelectItem>
                <SelectItem value="rejected">Rechazados</SelectItem>
                <SelectItem value="all">Todos</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Summary KPI */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="metric-card">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Pendientes</span>
          <p className="text-2xl font-bold font-mono mt-2 text-amber-400">{pendingAuths.length}</p>
        </div>
        <div className="metric-card">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Monto Pendiente</span>
          <p className="text-2xl font-bold font-mono mt-2 text-amber-400">
            {formatCurrency(pendingAuths.reduce((sum, a) => sum + (a.movement_details?.monto_mxn || 0), 0))}
          </p>
        </div>
        <div className="metric-card">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Resueltos</span>
          <p className="text-2xl font-bold font-mono mt-2">{resolvedAuths.length}</p>
        </div>
      </div>

      {/* Pending Authorizations */}
      <Card>
        <CardHeader>
          <CardTitle className="font-heading text-lg flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-400" />
            Pendientes de Autorización ({pendingAuths.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : pendingAuths.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No hay autorizaciones pendientes con los filtros seleccionados
            </div>
          ) : (
            <div className="space-y-4">
              {pendingAuths.map(auth => {
                const mov = auth.movement_details;
                const ctx = auth.budget_context;
                
                return (
                  <div
                    key={auth.id}
                    className="p-4 border border-border rounded-lg bg-card hover:border-amber-500/30 transition-colors"
                    data-testid={`auth-item-${auth.id}`}
                  >
                    <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                      {/* Left: Movement Info */}
                      <div className="flex-1 space-y-3">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge variant="outline" className="text-amber-400 border-amber-500/30">
                            <Clock className="h-3 w-3 mr-1" />
                            Pendiente
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {formatDate(auth.created_at)}
                          </span>
                        </div>
                        
                        <p className="font-medium text-red-400">{auth.reason}</p>
                        
                        {mov && (
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                            {auth.purchase_order_details && (
                              <>
                                <div>
                                  <span className="text-xs text-muted-foreground">OC</span>
                                  <p className="font-medium">{auth.purchase_order_details.folio || "-"}</p>
                                </div>
                                <div>
                                  <span className="text-xs text-muted-foreground">Proveedor</span>
                                  <p className="font-medium">{auth.purchase_order_details.vendor_name || "-"}</p>
                                </div>
                              </>
                            )}
                            <div>
                              <span className="text-xs text-muted-foreground">Empresa</span>
                              <p className="font-medium">{mov.empresa_nombre}</p>
                            </div>
                            <div>
                              <span className="text-xs text-muted-foreground">Proyecto</span>
                              <p className="font-medium">{mov.project_code}</p>
                            </div>
                            <div>
                              <span className="text-xs text-muted-foreground">Partida(s)</span>
                              <p className="font-medium">{mov.partida_codigo || "-"}</p>
                            </div>
                            <div>
                              <span className="text-xs text-muted-foreground">RFC</span>
                              <p className="font-medium">{mov.provider_rfc || "-"}</p>
                            </div>
                            <div>
                              <span className="text-xs text-muted-foreground">Referencia (Factura)</span>
                              <p className="font-mono text-xs">{mov.referencia}</p>
                            </div>
                            <div>
                              <span className="text-xs text-muted-foreground">Monto</span>
                              <p className="font-mono font-bold text-amber-400">{formatCurrency(mov.monto_mxn)}</p>
                            </div>
                          </div>
                        )}
                        
                        {/* Budget Impact Preview */}
                        {ctx && (
                          <div className="mt-3 p-3 bg-muted/50 rounded-lg">
                            <p className="text-xs font-medium mb-2 flex items-center gap-1">
                              <TrendingUp className="h-3 w-3" />
                              Impacto en Presupuesto:
                            </p>
                            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
                              <div>
                                <span className="text-muted-foreground">Presupuesto</span>
                                <p className="font-mono">{formatCurrency(ctx.presupuesto)}</p>
                              </div>
                              <div>
                                <span className="text-muted-foreground">Ejecutado Actual</span>
                                <p className="font-mono">{formatCurrency(ctx.ejecutado_actual)}</p>
                              </div>
                              <div>
                                <span className="text-muted-foreground">Este Mov.</span>
                                <p className="font-mono text-amber-400">+{formatCurrency(ctx.monto_movimiento)}</p>
                              </div>
                              <div>
                                <span className="text-muted-foreground">% Actual</span>
                                <p className="font-mono">{ctx.porcentaje_actual?.toFixed(1)}%</p>
                              </div>
                              <div>
                                <span className="text-muted-foreground">% Si Aprueba</span>
                                <p className={`font-mono font-bold ${ctx.porcentaje_si_aprueba > 100 ? 'text-red-400' : 'text-emerald-400'}`}>
                                  {ctx.porcentaje_si_aprueba?.toFixed(1)}%
                                </p>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                      
                      {/* Right: Action Buttons */}
                      {canResolve && (
                        <div className="flex lg:flex-col gap-2">
                          <Button
                            size="sm"
                            className="bg-emerald-600 hover:bg-emerald-700"
                            onClick={() => openResolveDialog(auth, "approved")}
                            disabled={resolving === auth.id}
                            data-testid={`approve-auth-${auth.id}`}
                          >
                            <CheckCircle className="h-4 w-4 mr-1" />
                            Aprobar / Parcial
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-red-400 border-red-500/30 hover:bg-red-500/10"
                            onClick={() => openResolveDialog(auth, "rejected")}
                            disabled={resolving === auth.id}
                            data-testid={`reject-auth-${auth.id}`}
                          >
                            <XCircle className="h-4 w-4 mr-1" />
                            Rechazar
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Resolved History */}
      {resolvedAuths.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="font-heading text-lg flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Historial de Autorizaciones
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="data-table" data-testid="auth-history-table">
                <thead>
                  <tr>
                    <th>Fecha Solicitud</th>
                    <th>Proyecto</th>
                    <th>Partida</th>
                    <th>Monto</th>
                    <th>Razón</th>
                    <th>Estado</th>
                    <th>Fecha Resolución</th>
                    <th>Notas</th>
                  </tr>
                </thead>
                <tbody>
                  {resolvedAuths.map(auth => {
                    const config = statusConfig[auth.status];
                    const Icon = config?.icon || Clock;
                    const mov = auth.movement_details;
                    
                    return (
                      <tr key={auth.id}>
                        <td className="font-mono text-sm">{formatDate(auth.created_at)}</td>
                        <td>{mov?.project_code || "N/A"}</td>
                        <td>{mov?.partida_codigo || "N/A"}</td>
                        <td className="font-mono">{mov ? formatCurrency(mov.monto_mxn) : "N/A"}</td>
                        <td className="max-w-[200px] truncate">{auth.reason}</td>
                        <td>
                          <Badge variant="outline" className={`${config?.color} ${config?.bg}`}>
                            <Icon className="h-3 w-3 mr-1" />
                            {config?.label}
                          </Badge>
                        </td>
                        <td className="font-mono text-sm">
                          {auth.resolved_at ? formatDate(auth.resolved_at) : "-"}
                        </td>
                        <td className="text-muted-foreground text-sm max-w-[150px] truncate">
                          {auth.notes || "-"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Resolve Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className={action === "approved" ? "text-emerald-400" : "text-red-400"}>
              {action === "approved" ? "✓ Aprobar Movimiento" : "✕ Rechazar Movimiento"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-4 bg-muted rounded-lg">
              <p className="font-medium mb-2">{selectedAuth?.reason}</p>
              {selectedAuth?.movement_details && (
                <div className="text-sm space-y-1">
                  <p>Proyecto: <span className="font-mono">{selectedAuth.movement_details.project_code}</span></p>
                  <p>Monto: <span className="font-mono font-bold">{formatCurrency(selectedAuth.movement_details.monto_mxn)}</span></p>
                </div>
              )}
            </div>
            
            {action === "approved" && selectedSummary && (
              <div className="p-3 bg-emerald-500/10 rounded-lg border border-emerald-500/20 space-y-1 text-sm">
                <p>Presupuesto total: <span className="font-mono font-semibold">{formatCurrency(selectedSummary.presupuesto_total)}</span></p>
                <p>Disponible actual: <span className="font-mono font-semibold">{formatCurrency(selectedSummary.disponible_actual)}</span></p>
                <p>Monto total OC: <span className="font-mono">{formatCurrency(totalOc)}</span></p>
                <p>Aprobado acumulado: <span className="font-mono">{formatCurrency(approvedAccumulated)}</span></p>
                <p>Pendiente OC: <span className="font-mono">{formatCurrency(pendingAmount)}</span></p>
                <p>Restante proyectado si aprueba pendiente completo: <span className="font-mono">{formatCurrency(selectedSummary.restante_proyectado_si_aprueba)}</span></p>
                {partialAmount !== "" && (
                  <p>Restante proyectado con parcial capturado: <span className="font-mono font-semibold">{formatCurrency(projectedRemainingIfPartial)}</span></p>
                )}
              </div>
            )}
            
            <div className="space-y-2">
              <label className="text-sm font-medium">
                {action === "rejected" ? "Motivo del rechazo (requerido)" : "Notas (opcional)"}
              </label>
              <Textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={action === "rejected" 
                  ? "Explique el motivo del rechazo..." 
                  : "Agregar comentarios sobre la aprobación..."
                }
                rows={3}
                data-testid="auth-notes-input"
                className={action === "rejected" && !notes.trim() ? "border-red-500" : ""}
              />
              {action === "rejected" && !notes.trim() && (
                <p className="text-xs text-red-400">* El motivo es obligatorio para rechazar</p>
              )}
            </div>

            {action === "approved" && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Monto parcial a aprobar (opcional)</label>
                <input
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={partialAmount}
                  onChange={(e) => setPartialAmount(e.target.value)}
                  placeholder="Vacío = aprobar monto completo pendiente"
                />
              </div>
            )}
          </div>
            {resolveError && (
              <div className="rounded-md border border-red-500/30 bg-red-500/10 p-2 text-sm text-red-300">{resolveError}</div>
            )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={handleResolve}
              disabled={resolving || (action === "rejected" && !notes.trim())}
              className={action === "approved" 
                ? "bg-emerald-600 hover:bg-emerald-700" 
                : "bg-red-600 hover:bg-red-700"
              }
              data-testid="confirm-auth-btn"
            >
              {resolving && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              {action === "approved" ? "Confirmar Aprobación" : "Confirmar Rechazo"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Authorizations;
