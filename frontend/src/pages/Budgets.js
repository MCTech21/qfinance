import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import { Plus, Pencil, Trash2, Loader2 } from "lucide-react";
import { buildYearOptions } from "../lib/yearRange";

const Budgets = () => {
  const { api, canManage, user } = useAuth();
  const [budgets, setBudgets] = useState([]);
  const [projects, setProjects] = useState([]);
  const [partidas, setPartidas] = useState([]);
  const [empresas, setEmpresas] = useState([]);
  const [budgetRequests, setBudgetRequests] = useState([]);
  const [yearOptions] = useState(buildYearOptions());
  const [isLoading, setIsLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingBudget, setEditingBudget] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isResolving, setIsResolving] = useState(false);
  
  const [filters, setFilters] = useState({
    empresa_id: "all",
    project_id: "all",
    year: new Date().getFullYear(),
    month: new Date().getMonth() + 1
  });
  
  const [formData, setFormData] = useState({
    project_id: "",
    partida_codigo: "",
    total_amount: "",
    annual_json: "{}",
    monthly_json: "{}",
    notes: ""
  });

  const months = [
    { value: 1, label: "Enero" }, { value: 2, label: "Febrero" }, { value: 3, label: "Marzo" },
    { value: 4, label: "Abril" }, { value: 5, label: "Mayo" }, { value: 6, label: "Junio" },
    { value: 7, label: "Julio" }, { value: 8, label: "Agosto" }, { value: 9, label: "Septiembre" },
    { value: 10, label: "Octubre" }, { value: 11, label: "Noviembre" }, { value: 12, label: "Diciembre" },
  ];

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [budgetsRes, projectsRes, partidasRes, empresasRes, budgetRequestsRes] = await Promise.all([
        api().get("/budgets", {
          params: {
            project_id: filters.project_id !== "all" ? filters.project_id : undefined,
          }
        }),
        api().get("/projects", { params: { empresa_id: filters.empresa_id !== "all" ? filters.empresa_id : undefined } }),
        api().get("/catalogo-partidas"),
        api().get("/empresas"),
        api().get("/budget-requests")
      ]);
      setBudgets(budgetsRes.data);
      setProjects(projectsRes.data);
      setPartidas(partidasRes.data);
      setEmpresas(empresasRes.data);
      setBudgetRequests(budgetRequestsRes.data);
    } catch (error) {
      toast.error("Error al cargar presupuestos");
    } finally {
      setIsLoading(false);
    }
  }, [api, filters]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleOpenDialog = (budget = null) => {
    if (budget) {
      setEditingBudget(budget);
      setFormData({
        project_id: budget.project_id,
        partida_codigo: budget.partida_codigo,
        total_amount: budget.total_amount || "0",
        annual_json: JSON.stringify(budget.annual_breakdown || {}, null, 2),
        monthly_json: JSON.stringify(budget.monthly_breakdown || {}, null, 2),
        notes: budget.notes || ""
      });
    } else {
      setEditingBudget(null);
      setFormData({
        project_id: "",
        partida_codigo: "",
        total_amount: "",
        annual_json: "{}",
        monthly_json: "{}",
        notes: ""
      });
    }
    setDialogOpen(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    
    try {
      const payload = {
        project_id: formData.project_id,
        partida_codigo: formData.partida_codigo,
        total_amount: formData.total_amount || "0",
        annual_breakdown: JSON.parse(formData.annual_json || "{}"),
        monthly_breakdown: JSON.parse(formData.monthly_json || "{}"),
        notes: formData.notes,
      };

      if (editingBudget) {
        await api().put(`/budgets/${editingBudget.id}`, payload);
        toast.success("Presupuesto actualizado");
      } else {
        await api().post('/budgets', payload);
        toast.success("Presupuesto creado");
      }
      
      setDialogOpen(false);
      fetchData();
    } catch (error) {
      const detail = error.response?.data?.detail;
      const code = detail?.code;
      const codeMap = { annual_sum_exceeds_total: "La suma anual excede el total", monthly_sum_exceeds_annual: "La suma mensual excede el anual", monthly_sum_exceeds_total: "La suma mensual excede el total" };
      toast.error(codeMap[code] || detail?.message || detail || "Error al guardar presupuesto");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (budget) => {
    if (!window.confirm("¿Eliminar este presupuesto?")) return;
    
    try {
      await api().delete(`/budgets/${budget.id}`);
      toast.success("Presupuesto eliminado");
      fetchData();
    } catch (error) {
      toast.error("Error al eliminar presupuesto");
    }
  };

  const handleResolveRequest = async (requestId, status) => {
    setIsResolving(true);
    try {
      await api().put(`/budget-requests/${requestId}/resolve`, { status, notes: status === "approved" ? "Aprobado desde Presupuestos" : "Rechazado desde Presupuestos" });
      toast.success(status === "approved" ? "Solicitud aprobada" : "Solicitud rechazada");
      await fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al resolver solicitud");
    } finally {
      setIsResolving(false);
    }
  };

  const formatCurrency = (num) => {
    return new Intl.NumberFormat("es-MX", {
      style: "currency",
      currency: "MXN",
      minimumFractionDigits: 0,
    }).format(num);
  };

  const getProjectName = (id) => projects.find(p => p.id === id)?.name || "N/A";
  const getPartidaName = (codigo) => partidas.find(p => p.codigo === codigo)?.nombre || "N/A";
  const getPartidaCode = (codigo) => partidas.find(p => p.codigo === codigo)?.codigo || "N/A";

  return (
    <div className="space-y-6" data-testid="budgets-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight">Presupuestos</h1>
          <p className="text-muted-foreground">Gestión de presupuestos por proyecto y partida</p>
        </div>
        
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={() => handleOpenDialog()} data-testid="add-budget-btn">
              <Plus className="h-4 w-4 mr-2" />
              {user?.role === "finanzas" ? "Solicitar Presupuesto" : "Nuevo Presupuesto"}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{editingBudget ? "Editar Presupuesto" : (user?.role === "finanzas" ? "Solicitar Presupuesto" : "Nuevo Presupuesto")}</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Proyecto</Label>
                  <Select
                    value={formData.project_id}
                    onValueChange={(v) => setFormData(prev => ({ ...prev, project_id: v }))}
                  >
                    <SelectTrigger data-testid="budget-project-select">
                      <SelectValue placeholder="Seleccionar..." />
                    </SelectTrigger>
                    <SelectContent>
                      {projects.map(p => (
                        <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Partida</Label>
                  <Select
                    value={formData.partida_codigo}
                    onValueChange={(v) => setFormData(prev => ({ ...prev, partida_codigo: v }))}
                  >
                    <SelectTrigger data-testid="budget-partida-select">
                      <SelectValue placeholder="Seleccionar..." />
                    </SelectTrigger>
                    <SelectContent>
                      {partidas.map(p => (
                        <SelectItem key={p.codigo} value={p.codigo}>{p.codigo} - {p.nombre}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <div className="space-y-2">
                <Label>Total</Label>
                <Input
                  type="text"
                  value={formData.total_amount}
                  onChange={(e) => setFormData(prev => ({ ...prev, total_amount: e.target.value }))}
                  placeholder="0.00"
                  required
                  data-testid="budget-total-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Desglose anual (JSON)</Label>
                <textarea className="w-full min-h-20 border rounded-md p-2 text-sm" value={formData.annual_json} onChange={(e) => setFormData(prev => ({ ...prev, annual_json: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Desglose mensual (JSON)</Label>
                <textarea className="w-full min-h-20 border rounded-md p-2 text-sm" value={formData.monthly_json} onChange={(e) => setFormData(prev => ({ ...prev, monthly_json: e.target.value }))} />
              </div>
              
              <div className="space-y-2">
                <Label>Notas</Label>
                <Input
                  value={formData.notes}
                  onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                  placeholder="Notas adicionales..."
                />
              </div>
              
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={isSaving} data-testid="budget-submit-btn">
                  {isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  {editingBudget ? "Actualizar" : "Crear"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-4">
            <Select
              value={filters.empresa_id}
              onValueChange={(v) => setFilters(prev => ({ ...prev, empresa_id: v, project_id: "all" }))}
            >
              <SelectTrigger className="w-[220px]">
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
              <SelectTrigger className="w-[200px]" data-testid="filter-project">
                <SelectValue placeholder="Proyecto" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los proyectos</SelectItem>
                {projects.map(p => (
                  <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
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
          <CardTitle className="font-heading text-lg">Lista de Presupuestos</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : budgets.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No hay presupuestos para el período seleccionado
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table" data-testid="budgets-table">
                <thead>
                  <tr>
                    <th>Proyecto</th>
                    <th>Partida</th>
                    <th>Estado</th>
                    <th className="text-right">Total</th>
                    <th>Notas</th>
                    <th className="text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {budgets.map(budget => (
                    <tr key={budget.id}>
                      <td>{getProjectName(budget.project_id)}</td>
                      <td>
                        <span className="font-mono text-xs text-muted-foreground mr-2">
                          {getPartidaCode(budget.partida_codigo)}
                        </span>
                        {getPartidaName(budget.partida_codigo)}
                      </td>
                      <td><Badge variant="outline">{budget.approval_status || "legacy"}</Badge></td>
                      <td className="mono-number">{formatCurrency(Number(budget.total_amount || budget.amount_mxn || 0))}</td>
                      <td className="text-muted-foreground text-sm">{budget.notes || "-"}</td>
                      <td className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleOpenDialog(budget)}
                            data-testid={`edit-budget-${budget.id}`}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          {canManage() && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDelete(budget)}
                              className="text-destructive hover:text-destructive"
                              data-testid={`delete-budget-${budget.id}`}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {user?.role === "finanzas" && (
        <Card>
          <CardHeader><CardTitle className="font-heading text-lg">Solicitudes de presupuesto</CardTitle></CardHeader>
          <CardContent>
            {budgetRequests.length === 0 ? <div className="text-sm text-muted-foreground">Sin solicitudes</div> : (
              <ul className="space-y-2 text-sm">
                {budgetRequests.map((r) => (
                  <li key={r.id}>{r.partida_codigo} / {r.year}-{String(r.month).padStart(2, "0")} - ${r.amount_mxn} <span className="text-muted-foreground">({r.status})</span></li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      {user?.role === "admin" && (
        <Card>
          <CardHeader><CardTitle className="font-heading text-lg">Solicitudes pendientes</CardTitle></CardHeader>
          <CardContent>
            {(budgetRequests || []).filter((r) => r.status === "pending").length === 0 ? (
              <div className="text-sm text-muted-foreground">Sin solicitudes pendientes</div>
            ) : (
              <div className="space-y-3">
                {(budgetRequests || []).filter((r) => r.status === "pending").map((r) => (
                  <div key={r.id} className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 border border-border rounded-md p-3">
                    <div className="text-sm">
                      <div><span className="font-mono">{r.partida_codigo}</span> / {r.year}-{String(r.month).padStart(2, "0")}</div>
                      <div className="text-muted-foreground">Monto: {formatCurrency(r.amount_mxn)}</div>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" disabled={isResolving} onClick={() => handleResolveRequest(r.id, "approved")}>Aprobar</Button>
                      <Button size="sm" variant="destructive" disabled={isResolving} onClick={() => handleResolveRequest(r.id, "rejected")}>Rechazar</Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default Budgets;
