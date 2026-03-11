import { buildYearOptions } from "../lib/yearRange";
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import KPICard from "../components/KPICard";
import TrafficLight from "../components/TrafficLight";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Wallet, TrendingUp, AlertTriangle, CheckCircle, Building, Landmark } from "lucide-react";

const Dashboard = () => {
  const { api, allowedCompanies, user } = useAuth();
  const [dashboardData, setDashboardData] = useState(null);
  const [empresas, setEmpresas] = useState([]);
  const [projects, setProjects] = useState([]);
  const [filteredProjects, setFilteredProjects] = useState([]);
  const [selectedEmpresa, setSelectedEmpresa] = useState("all");
  const [selectedProject, setSelectedProject] = useState("all");
  const [selectedYear, setSelectedYear] = useState(2025);
  const [selectedMonth, setSelectedMonth] = useState(1);
  const [selectedQuarter, setSelectedQuarter] = useState(1);
  const [selectedPeriod, setSelectedPeriod] = useState("month");
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);

  const yearOptions = buildYearOptions();
  const isAdmin = user?.role === "admin";

  const months = [
    { value: 1, label: "Enero" }, { value: 2, label: "Febrero" }, { value: 3, label: "Marzo" },
    { value: 4, label: "Abril" }, { value: 5, label: "Mayo" }, { value: 6, label: "Junio" },
    { value: 7, label: "Julio" }, { value: 8, label: "Agosto" }, { value: 9, label: "Septiembre" },
    { value: 10, label: "Octubre" }, { value: 11, label: "Noviembre" }, { value: 12, label: "Diciembre" },
  ];

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setIsError(false);
    try {
      const params = { empresa_id: selectedEmpresa, project_id: selectedProject, period: selectedPeriod, year: selectedYear };
      if (selectedPeriod === "month") params.month = selectedMonth;
      if (selectedPeriod === "quarter") params.quarter = selectedQuarter;
      const [reportsRes, empresasRes, projectsRes] = await Promise.all([
        api().get("/reports/dashboard", { params }),
        api().get("/empresas"),
        api().get("/projects"),
      ]);
      setDashboardData(reportsRes.data);
      const permitted = isAdmin ? (empresasRes.data || []) : (empresasRes.data || []).filter((e) => (allowedCompanies || []).some((ac) => ac.id === e.id));
      setEmpresas(permitted);
      setProjects(projectsRes.data || []);
    } catch (error) {
      setIsError(true);
      toast.error(error?.response?.data?.detail?.message || "Error al cargar dashboard");
    } finally {
      setIsLoading(false);
    }
  }, [api, selectedEmpresa, selectedProject, selectedYear, selectedMonth, selectedQuarter, selectedPeriod, allowedCompanies, isAdmin]);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    const scopedProjects = selectedEmpresa === "all" ? projects : projects.filter((p) => p.empresa_id === selectedEmpresa);
    setFilteredProjects(isAdmin ? scopedProjects : scopedProjects.filter((p) => (allowedCompanies || []).some((c) => c.id === p.empresa_id)));
    setSelectedProject("all");
  }, [selectedEmpresa, projects, allowedCompanies, isAdmin]);

  const formatCurrency = (num) => new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(num || 0);
  const formatPct = (num) => (num === null || num === undefined ? "N/A" : `${Number(num).toFixed(2)}%`);

  if (isLoading) return <div className="space-y-6 animate-pulse"><div className="h-8 w-48 bg-muted rounded" /></div>;

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight">Dashboard Gerencial P&amp;L</h1>
          <p className="text-muted-foreground">{dashboardData?.filtros?.period_label || "Resumen financiero"}</p>
        </div>

        <div className="flex flex-wrap gap-3">
          <Select value={selectedEmpresa} onValueChange={setSelectedEmpresa}>
            <SelectTrigger className="w-[200px]"><SelectValue placeholder="Empresa" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas las empresas</SelectItem>
              {empresas.map((e) => <SelectItem key={e.id} value={e.id}>{e.nombre}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={selectedProject} onValueChange={setSelectedProject}><SelectTrigger className="w-[180px]"><SelectValue placeholder="Proyecto" /></SelectTrigger><SelectContent><SelectItem value="all">Todos los proyectos</SelectItem>{filteredProjects.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent></Select>
          <Select value={selectedPeriod} onValueChange={setSelectedPeriod}><SelectTrigger className="w-[150px]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="month">Mensual</SelectItem><SelectItem value="quarter">Trimestral</SelectItem><SelectItem value="year">Anual</SelectItem></SelectContent></Select>
          {selectedPeriod === "month" && <Select value={String(selectedMonth)} onValueChange={(v) => setSelectedMonth(Number(v))}><SelectTrigger className="w-[140px]"><SelectValue /></SelectTrigger><SelectContent>{months.map((m) => <SelectItem key={m.value} value={String(m.value)}>{m.label}</SelectItem>)}</SelectContent></Select>}
          {selectedPeriod === "quarter" && <Select value={String(selectedQuarter)} onValueChange={(v) => setSelectedQuarter(Number(v))}><SelectTrigger className="w-[120px]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="1">Q1</SelectItem><SelectItem value="2">Q2</SelectItem><SelectItem value="3">Q3</SelectItem><SelectItem value="4">Q4</SelectItem></SelectContent></Select>}
          <Select value={String(selectedYear)} onValueChange={(v) => setSelectedYear(Number(v))}><SelectTrigger className="w-[100px]"><SelectValue /></SelectTrigger><SelectContent>{yearOptions.map((y) => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}</SelectContent></Select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4" data-testid="kpi-grid">
        <KPICard title="Ingreso proyectado 405" value={dashboardData?.totals?.ingreso_proyectado_405 || 0} icon={Landmark} subtitle="Inventario" />
        <KPICard title="Presupuesto total" value={dashboardData?.totals?.presupuesto_total || 0} icon={Wallet} subtitle="Budgets" />
        <KPICard title="Real ejecutado" value={dashboardData?.totals?.ejecutado_total || 0} icon={TrendingUp} variant="inverse" />
        <KPICard title="Por ejercer" value={dashboardData?.totals?.por_ejercer_total || 0} icon={(dashboardData?.totals?.por_ejercer_total || 0) >= 0 ? CheckCircle : AlertTriangle} />
        <Card><CardContent className="pt-6"><TrafficLight status={dashboardData?.totals?.traffic_light} percentage={dashboardData?.totals?.ejecucion_vs_ingreso_pct || 0} size="lg" /></CardContent></Card>
      </div>

      {isError ? <Card><CardContent className="pt-6 text-muted-foreground">No se pudo cargar el dashboard.</CardContent></Card> : null}

      <Card><CardHeader><CardTitle className="font-heading text-lg flex items-center gap-2"><Building className="h-5 w-5" />Estado de resultados (P&amp;L)</CardTitle></CardHeader><CardContent>
        {!(dashboardData?.rows || []).length ? <p className="text-muted-foreground" data-testid="empty-state">Sin datos para los filtros seleccionados.</p> : (
          <div className="overflow-x-auto"><table className="data-table" data-testid="pl-table"><thead><tr><th>Concepto</th><th className="text-right">% s/ ingreso</th><th className="text-right">Presupuesto</th><th className="text-right">Real</th><th className="text-right">Por ejercer</th><th>Semáforo</th></tr></thead><tbody>
            {(dashboardData?.rows || []).map((row, idx) => (
              <tr key={`${row.code}-${idx}`} className={row.row_type === "subtotal" ? "font-semibold bg-muted/20" : ""}>
                <td>{row.code} {row.name}</td>
                <td className="mono-number text-right">{formatPct(row.income_pct)}</td>
                <td className="mono-number text-right">{formatCurrency(row.budget)}</td>
                <td className="mono-number text-right">{formatCurrency(row.real)}</td>
                <td className="mono-number text-right">{formatCurrency(row.remaining)}</td>
                <td><TrafficLight status={row.traffic_light} showLabel={false} size="sm" /></td>
              </tr>
            ))}
          </tbody></table></div>
        )}
      </CardContent></Card>
    </div>
  );
};

export default Dashboard;
