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

const parseAnnualBreakdownToRows = (annualBreakdown = {}) => {
  if (!annualBreakdown || typeof annualBreakdown !== "object") return [];
  return Object.entries(annualBreakdown)
    .map(([year, amount]) => ({ id: `${year}`, year: String(year), amount: String(amount ?? "") }))
    .sort((a, b) => Number(a.year) - Number(b.year));
};

const parseMonthlyBreakdownToRows = (monthlyBreakdown = {}) => {
  if (!monthlyBreakdown || typeof monthlyBreakdown !== "object") return [];
  return Object.entries(monthlyBreakdown)
    .map(([ym, amount]) => {
      const [year = "", month = ""] = String(ym).split("-");
      return { id: `${ym}`, year: String(year), month: String(Number(month) || ""), amount: String(amount ?? "") };
    })
    .filter((row) => row.year && row.month)
    .sort((a, b) => {
      const ay = Number(a.year); const by = Number(b.year);
      if (ay !== by) return ay - by;
      return Number(a.month) - Number(b.month);
    });
};

const rowsToAnnualBreakdown = (rows = []) => {
  const out = {};
  rows.forEach((row) => {
    out[String(row.year)] = String(row.amount);
  });
  return out;
};

const rowsToMonthlyBreakdown = (rows = []) => {
  const out = {};
  rows.forEach((row) => {
    const key = `${String(row.year)}-${String(row.month).padStart(2, "0")}`;
    out[key] = String(row.amount);
  });
  return out;
};

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
    year: "all",
    month: "all"
  });
  
  const [formData, setFormData] = useState({
    project_id: "",
    partida_codigo: "",
    total_amount: "",
    annual_rows: [],
    monthly_rows: [],
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
            empresa_id: filters.empresa_id !== "all" ? filters.empresa_id : undefined,
            project_id: filters.project_id !== "all" ? filters.project_id : undefined,
            year: filters.year !== "all" ? Number(filters.year) : undefined,
            month: (filters.year !== "all" && filters.month !== "all") ? Number(filters.month) : undefined,
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
        annual_rows: parseAnnualBreakdownToRows(budget.annual_breakdown),
        monthly_rows: parseMonthlyBreakdownToRows(budget.monthly_breakdown),
        notes: budget.notes || ""
      });
    } else {
      setEditingBudget(null);
      setFormData({
        project_id: "",
        partida_codigo: "",
        total_amount: "",
        annual_rows: [],
        monthly_rows: [],
        notes: ""
      });
    }
    setDialogOpen(true);
  };

  const validateBreakdownRows = () => {
    for (const row of formData.annual_rows) {
      if (!row.year || Number.isNaN(Number(row.year))) throw new Error("Cada fila anual requiere año válido");
      if (Number(row.amount) < 0 || Number.isNaN(Number(row.amount))) throw new Error("Cada fila anual requiere monto numérico >= 0");
    }
    for (const row of formData.monthly_rows) {
      if (!row.year || Number.isNaN(Number(row.year))) throw new Error("Cada fila mensual requiere año válido");
      if (!row.month || Number(row.month) < 1 || Number(row.month) > 12) throw new Error("Cada fila mensual requiere mes entre 1 y 12");
      if (Number(row.amount) < 0 || Number.isNaN(Number(row.amount))) throw new Error("Cada fila mensual requiere monto numérico >= 0");
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    
    try {
      validateBreakdownRows();
      const payload = {
        project_id: formData.project_id,
        partida_codigo: formData.partida_codigo,
        total_amount: formData.total_amount || "0",
        annual_breakdown: rowsToAnnualBreakdown(formData.annual_rows),
        monthly_breakdown: rowsToMonthlyBreakdown(formData.monthly_rows),
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
      const codeMap = { annual_sum_exceeds_total: "La suma anual excede el total", monthly_sum_exceeds_annual: "La suma mensual excede el anual", monthly_sum_exceeds_total: "La suma mensual excede el total", invalid_breakdown_json: "El desglose debe ser JSON válido.", invalid_breakdown_type: "El desglose debe ser un objeto JSON (clave-valor).", invalid_breakdown_key: "Hay una clave inválida en el desglose.", invalid_breakdown_value: "Hay un monto inválido en el desglose." };
      toast.error(codeMap[code] || detail?.message || error?.message || detail || "Error al guardar presupuesto");
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

  const addAnnualRow = () => {
    setFormData((prev) => ({
      ...prev,
      annual_rows: [...prev.annual_rows, { id: crypto.randomUUID(), year: String(yearOptions[0] || 2025), amount: "0" }],
    }));
  };

  const updateAnnualRow = (id, patch) => {
    setFormData((prev) => ({
      ...prev,
      annual_rows: prev.annual_rows.map((row) => (row.id === id ? { ...row, ...patch } : row)),
    }));
  };

  const removeAnnualRow = (id) => {
    setFormData((prev) => ({ ...prev, annual_rows: prev.annual_rows.filter((row) => row.id !== id) }));
  };

  const addMonthlyRow = () => {
    setFormData((prev) => ({
      ...prev,
      monthly_rows: [...prev.monthly_rows, { id: crypto.randomUUID(), year: String(yearOptions[0] || 2025), month: "1", amount: "0" }],
    }));
  };

  const updateMonthlyRow = (id, patch) => {
    setFormData((prev) => ({
      ...prev,
      monthly_rows: prev.monthly_rows.map((row) => (row.id === id ? { ...row, ...patch } : row)),
    }));
  };

  const removeMonthlyRow = (id) => {
    setFormData((prev) => ({ ...prev, monthly_rows: prev.monthly_rows.filter((row) => row.id !== id) }));
  };

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
                <div className="flex items-center justify-between">
                  <Label>Desglose anual</Label>
                  <Button type="button" variant="outline" size="sm" onClick={addAnnualRow}>Agregar año</Button>
                </div>
                <div className="space-y-2 rounded-md border border-border bg-card/60 p-3">
                  {formData.annual_rows.length === 0 && <p className="text-xs text-muted-foreground">Sin desglose anual (se usará total).</p>}
                  {formData.annual_rows.map((row) => (
                    <div key={row.id} className="grid grid-cols-12 gap-2">
                      <Input className="col-span-4" type="number" min="2000" max="2100" value={row.year} onChange={(e) => updateAnnualRow(row.id, { year: e.target.value })} placeholder="Año" />
                      <Input className="col-span-6" type="number" min="0" step="0.01" value={row.amount} onChange={(e) => updateAnnualRow(row.id, { amount: e.target.value })} placeholder="Monto" />
                      <Button className="col-span-2" type="button" variant="ghost" onClick={() => removeAnnualRow(row.id)}>X</Button>
                    </div>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Desglose mensual</Label>
                  <Button type="button" variant="outline" size="sm" onClick={addMonthlyRow}>Agregar mes</Button>
                </div>
                <div className="space-y-2 rounded-md border border-border bg-card/60 p-3">
                  {formData.monthly_rows.length === 0 && <p className="text-xs text-muted-foreground">Sin desglose mensual (fallback anual/total).</p>}
                  {formData.monthly_rows.map((row) => (
                    <div key={row.id} className="grid grid-cols-12 gap-2">
                      <Input className="col-span-3" type="number" min="2000" max="2100" value={row.year} onChange={(e) => updateMonthlyRow(row.id, { year: e.target.value })} placeholder="Año" />
                      <Select value={String(row.month)} onValueChange={(v) => updateMonthlyRow(row.id, { month: v })}>
                        <SelectTrigger className="col-span-3"><SelectValue placeholder="Mes" /></SelectTrigger>
                        <SelectContent>
                          {months.map((m) => <SelectItem key={m.value} value={String(m.value)}>{m.label}</SelectItem>)}
                        </SelectContent>
                      </Select>
                      <Input className="col-span-4" type="number" min="0" step="0.01" value={row.amount} onChange={(e) => updateMonthlyRow(row.id, { amount: e.target.value })} placeholder="Monto" />
                      <Button className="col-span-2" type="button" variant="ghost" onClick={() => removeMonthlyRow(row.id)}>X</Button>
                    </div>
                  ))}
                </div>
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
              onValueChange={(v) => setFilters(prev => ({ ...prev, month: v }))}
              disabled={filters.year === "all"}
            >
              <SelectTrigger className="w-[140px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">TODO</SelectItem>
                {months.map(m => (
                  <SelectItem key={m.value} value={String(m.value)}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            <Select
              value={String(filters.year)}
              onValueChange={(v) => setFilters(prev => ({ ...prev, year: v, month: v === "all" ? "all" : prev.month }))}
            >
              <SelectTrigger className="w-[120px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">TODO</SelectItem>
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
              No hay presupuestos para el filtro seleccionado
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
                    <th className="text-right">Restante</th>
                    <th className="text-right">% Usado</th>
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
                      <td className="mono-number">{formatCurrency(Number(budget.remaining_total || 0))}</td>
                      <td className="mono-number">{Number(budget.usage_pct_total || 0).toFixed(1)}%</td>
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
