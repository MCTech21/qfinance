import { buildYearOptions } from "../lib/yearRange";
import { safeCurrency, safeNumber, safePercent } from "../lib/numberFormatters";
import { useState, useEffect, useMemo, useRef } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import KPICard from "../components/KPICard";
import TrafficLight from "../components/TrafficLight";
import DashboardSectionErrorBoundary from "../components/DashboardSectionErrorBoundary";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { Wallet, TrendingUp, AlertTriangle, CheckCircle, Building, Landmark, ShieldAlert, CircleAlert, BriefcaseBusiness } from "lucide-react";

const Dashboard = () => {
  const { api, allowedCompanies, user } = useAuth();
  const [dashboardData, setDashboardData] = useState(null);
  const [empresas, setEmpresas] = useState([]);
  const [projects, setProjects] = useState([]);
  const [filteredProjects, setFilteredProjects] = useState([]);
  const [selectedEmpresa, setSelectedEmpresa] = useState("all");
  const [selectedProject, setSelectedProject] = useState("all");
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(1);
  const [selectedQuarter, setSelectedQuarter] = useState(1);
  const [selectedPeriod, setSelectedPeriod] = useState("all");
  const [activeTab, setActiveTab] = useState("pnl");
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);

  const yearOptions = buildYearOptions();
  const isAdmin = user?.role === "admin";
  const abortRef = useRef(null);
  const requestKeyRef = useRef(null);
  const apiClient = useMemo(() => api(), [api]);

  const months = [
    { value: 1, label: "Enero" }, { value: 2, label: "Febrero" }, { value: 3, label: "Marzo" },
    { value: 4, label: "Abril" }, { value: 5, label: "Mayo" }, { value: 6, label: "Junio" },
    { value: 7, label: "Julio" }, { value: 8, label: "Agosto" }, { value: 9, label: "Septiembre" },
    { value: 10, label: "Octubre" }, { value: 11, label: "Noviembre" }, { value: 12, label: "Diciembre" },
  ];

  const requestParams = useMemo(() => {
    const params = {
      empresa_id: selectedEmpresa || "all",
      project_id: selectedProject || "all",
      period: selectedPeriod || "all",
      year: selectedYear,
    };
    if (params.period === "month") params.month = selectedMonth;
    if (params.period === "quarter") params.quarter = selectedQuarter;
    return params;
  }, [selectedEmpresa, selectedProject, selectedPeriod, selectedYear, selectedMonth, selectedQuarter]);

  useEffect(() => {
    const scopedProjects = selectedEmpresa === "all" ? projects : projects.filter((p) => p.empresa_id === selectedEmpresa);
    const scoped = isAdmin ? scopedProjects : scopedProjects.filter((p) => (allowedCompanies || []).some((c) => c.id === p.empresa_id));
    setFilteredProjects(scoped);
    const currentSelectionIsValid = selectedProject === "all" || scoped.some((p) => p.id === selectedProject);
    if (!currentSelectionIsValid) {
      setSelectedProject("all");
    }
  }, [selectedEmpresa, projects, allowedCompanies, isAdmin, selectedProject]);

  useEffect(() => {
    const fetchScopeOptions = async () => {
      try {
        const [empresasRes, projectsRes] = await Promise.all([apiClient.get("/empresas"), apiClient.get("/projects")]);
        const permitted = isAdmin ? (empresasRes.data || []) : (empresasRes.data || []).filter((e) => (allowedCompanies || []).some((ac) => ac.id === e.id));
        setEmpresas(permitted);
        setProjects(projectsRes.data || []);
      } catch (error) {
        toast.error(error?.response?.data?.detail?.message || "Error al cargar catálogo de filtros");
      }
    };

    fetchScopeOptions();
  }, [apiClient, allowedCompanies, isAdmin]);

  useEffect(() => {
    const key = JSON.stringify(requestParams);
    if (requestKeyRef.current === key) return;
    requestKeyRef.current = key;

    if (abortRef.current) {
      abortRef.current.abort();
    }

    const controller = new AbortController();
    abortRef.current = controller;

    const fetchDashboard = async () => {
      setIsLoading(true);
      setIsError(false);
      try {
        const reportsRes = await apiClient.get("/reports/dashboard", { params: requestParams, signal: controller.signal });
        if (!controller.signal.aborted) {
          setDashboardData(reportsRes.data);
        }
      } catch (error) {
        if (error?.name === "CanceledError" || error?.code === "ERR_CANCELED" || controller.signal.aborted) {
          return;
        }
        setIsError(true);
        toast.error(error?.response?.data?.detail?.message || "Error al cargar dashboard");
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    };

    fetchDashboard();

    return () => controller.abort();
  }, [apiClient, requestParams]);

  const formatCurrency = (num) => safeCurrency(num, { fallback: "S/I" });
  const formatPct = (num) => safePercent(num, { fallback: "S/I", fractionDigits: 2 });

  const shared = dashboardData?.shared_kpis || {};
  const pnlRows = dashboardData?.pnl?.rows || dashboardData?.rows || [];
  const budgetRows = dashboardData?.budget_control?.rows || [];
  const budgetSummary = dashboardData?.budget_control?.summary || {};
  const projection = dashboardData?.financial_projection || {};
  const projectionRows = projection?.rows || [];
  const projectionKpis = projection?.kpis || {};
  const projectionAssumptions = projection?.assumptions || [];
  const projectionEmptyReason = projection?.empty_reason;
  const budgetControlEmptyReason = dashboardData?.budget_control?.empty_reason;
  const pnlEmptyReason = dashboardData?.pnl?.empty_reason;
  const ingreso405 = shared.ingreso_proyectado_405 ?? dashboardData?.totals?.ingreso_proyectado_405;
  const hasProjectedIncomeSource = (dashboardData?.meta?.income_source || "none") !== "none";
  const hasProjectedIncome = hasProjectedIncomeSource && safeNumber(ingreso405) !== null;
  const porEjercerValue = safeNumber(shared.por_ejercer ?? dashboardData?.totals?.por_ejercer_total);
  const realVentas = shared?.real_ventas_402_403 ?? null;
  const metaVentas = shared?.meta_ventas_405 ?? null;
  const avanceVentasPct = shared?.avance_ventas_pct ?? null;
  const ventasTrafficLight =
    avanceVentasPct === null ? "neutral" :
    avanceVentasPct >= 100 ? "green" :
    avanceVentasPct >= 90 ? "yellow" : "red";
  const ventasColor = {
    green: "bg-green-500",
    yellow: "bg-yellow-400",
    red: "bg-red-500",
    neutral: "bg-gray-400",
  }[ventasTrafficLight];
  const utilityExpected = shared?.utility_expected?.gross || {};
  const utilityExpectedSubtitle = utilityExpected?.income_pct === null || utilityExpected?.income_pct === undefined
    ? "S/I"
    : `${Number(utilityExpected.income_pct).toFixed(2)}% s/ ingreso`;

  if (isLoading) return <div className="space-y-6 animate-pulse"><div className="h-8 w-48 bg-muted rounded" /></div>;

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground" data-testid="dashboard-subtitle">{dashboardData?.filtros?.period_label || "Resumen financiero"} · {dashboardData?.filtros?.empresa_nombre || "Todas"} · {dashboardData?.filtros?.project_nombre || "Todos"}</p>
        </div>

        <div className="flex flex-wrap gap-3">
          <Select value={selectedEmpresa} onValueChange={(value) => { setSelectedEmpresa(value || "all"); setSelectedProject("all"); }}>
            <SelectTrigger className="w-[200px]"><SelectValue placeholder="Empresa" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas las empresas</SelectItem>
              {empresas.map((e) => <SelectItem key={e.id} value={e.id}>{e.nombre}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={selectedProject} onValueChange={(value) => setSelectedProject(value || "all")}><SelectTrigger className="w-[180px]"><SelectValue placeholder="Proyecto" /></SelectTrigger><SelectContent><SelectItem value="all">Todos los proyectos</SelectItem>{filteredProjects.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent></Select>
          <Select value={selectedPeriod} onValueChange={(value) => setSelectedPeriod(value || "all")}><SelectTrigger className="w-[150px]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">TODO</SelectItem><SelectItem value="month">Mensual</SelectItem><SelectItem value="quarter">Trimestral</SelectItem><SelectItem value="year">Anual</SelectItem></SelectContent></Select>
          {selectedPeriod === "month" && <Select value={String(selectedMonth)} onValueChange={(v) => setSelectedMonth(Number(v))}><SelectTrigger className="w-[140px]"><SelectValue /></SelectTrigger><SelectContent>{months.map((m) => <SelectItem key={m.value} value={String(m.value)}>{m.label}</SelectItem>)}</SelectContent></Select>}
          {selectedPeriod === "quarter" && <Select value={String(selectedQuarter)} onValueChange={(v) => setSelectedQuarter(Number(v))}><SelectTrigger className="w-[120px]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="1">Q1</SelectItem><SelectItem value="2">Q2</SelectItem><SelectItem value="3">Q3</SelectItem><SelectItem value="4">Q4</SelectItem></SelectContent></Select>}
          <Select value={String(selectedYear)} onValueChange={(v) => setSelectedYear(Number(v))}><SelectTrigger className="w-[100px]"><SelectValue /></SelectTrigger><SelectContent>{yearOptions.map((y) => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}</SelectContent></Select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4" data-testid="kpi-grid">
        <KPICard title="Ingreso proyectado (base dashboard)" value={hasProjectedIncome ? ingreso405 : "S/I"} icon={Landmark} subtitle={hasProjectedIncome ? (dashboardData?.meta?.income_source_label || "Fuente disponible") : "Sin ingresos proyectados capturados"} />
        <KPICard title="Presupuesto total" value={shared.presupuesto_total ?? dashboardData?.totals?.presupuesto_total ?? null} icon={Wallet} subtitle="Budgets" />
        <KPICard title="Real ejecutado" value={shared.real_ejecutado ?? dashboardData?.totals?.ejecutado_total ?? null} icon={TrendingUp} variant="inverse" />
        <KPICard title="Por ejercer" value={shared.por_ejercer ?? dashboardData?.totals?.por_ejercer_total ?? null} icon={porEjercerValue === null || porEjercerValue >= 0 ? CheckCircle : AlertTriangle} />
        <KPICard title="Utilidad Bruta Esperada" value={utilityExpected?.amount ?? null} icon={Landmark} subtitle={utilityExpectedSubtitle} />
        <Card><CardContent className="pt-6"><TrafficLight status={dashboardData?.totals?.traffic_light} percentage={shared.ejecucion_vs_ingreso_pct ?? dashboardData?.totals?.ejecucion_vs_ingreso_pct} size="lg" /></CardContent></Card>
        {metaVentas !== null && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
                Avance de Ventas (402+403 vs 405)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between items-baseline">
                  <span className="text-2xl font-bold mono-number">
                    {avanceVentasPct !== null ? `${avanceVentasPct.toFixed(1)}%` : "S/I"}
                  </span>
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full text-white ${ventasColor}`}>
                    {ventasTrafficLight === "green" ? "Meta alcanzada" : ventasTrafficLight === "yellow" ? "Próximo" : "En curso"}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-700">
                  <div
                    className={`h-2.5 rounded-full transition-all ${ventasColor}`}
                    style={{ width: `${Math.min(avanceVentasPct ?? 0, 100)}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Cobrado: {formatCurrency(realVentas)}</span>
                  <span>Meta: {formatCurrency(metaVentas)}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {isError ? <Card><CardContent className="pt-6 text-muted-foreground" data-testid="error-state">No se pudo cargar el dashboard.</CardContent></Card> : null}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="pnl">P&amp;L</TabsTrigger>
          <TabsTrigger value="control">Control Presupuestal</TabsTrigger>
          <TabsTrigger value="projection">Proyección Financiera</TabsTrigger>
        </TabsList>

        <TabsContent value="pnl">
          <DashboardSectionErrorBoundary>
          <Card>
            <CardHeader><CardTitle className="font-heading text-lg flex items-center gap-2"><Building className="h-5 w-5" />Estado de resultados (P&amp;L)</CardTitle></CardHeader>
            <CardContent>
              {!pnlRows.length ? <p className="text-muted-foreground" data-testid="empty-state">{pnlEmptyReason || "Sin datos para los filtros seleccionados."}</p> : (
                <div className="overflow-x-auto"><table className="data-table" data-testid="pl-table"><thead><tr><th>Concepto</th><th className="text-right">% s/ ingreso</th><th className="text-right">Presupuesto</th><th className="text-right">Real</th><th className="text-right">Pendiente</th><th>Semáforo</th></tr></thead><tbody>
                  {pnlRows.map((row, idx) => (
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
            </CardContent>
          </Card>
          </DashboardSectionErrorBoundary>
        </TabsContent>

        <TabsContent value="control">
          <DashboardSectionErrorBoundary>
          <div className="space-y-4" data-testid="budget-control-view">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
              <KPICard title="Partidas en rojo" value={budgetSummary.red_count ?? null} icon={ShieldAlert} />
              <KPICard title="Partidas en amarillo" value={budgetSummary.yellow_count ?? null} icon={CircleAlert} />
              <KPICard title="Partidas con sobreejercicio" value={budgetSummary.overrun_count ?? null} icon={AlertTriangle} />
              <KPICard title="Comprometido total" value={budgetSummary.committed_total ?? null} icon={BriefcaseBusiness} />
              <KPICard title="Disponible total operativo" value={budgetSummary.available_total ?? null} icon={Wallet} />
            </div>

            <Card>
              <CardHeader><CardTitle className="font-heading text-lg">Control Presupuestal por partida</CardTitle></CardHeader>
              <CardContent>
                {!budgetRows.length ? <p className="text-muted-foreground" data-testid="budget-control-empty">{budgetControlEmptyReason || "Sin partidas presupuestales para los filtros seleccionados."}</p> : (
                  <div className="overflow-x-auto">
                    <table className="data-table" data-testid="budget-control-table">
                      <thead>
                        <tr>
                          <th>Código</th><th>Partida</th><th>Grupo</th>
                          <th className="text-right">Presupuesto</th><th className="text-right">Real</th><th className="text-right">Comprometido</th><th className="text-right">Disponible</th><th className="text-right">% Avance</th><th>Semáforo</th>
                        </tr>
                      </thead>
                      <tbody>
                        {budgetRows.map((row) => (
                          <tr key={row.code}>
                            <td>{row.code}</td>
                            <td>{row.name}</td>
                            <td>{row.group}</td>
                            <td className="mono-number text-right">{formatCurrency(row.budget)}</td>
                            <td className="mono-number text-right">{formatCurrency(row.real)}</td>
                            <td className="mono-number text-right">{formatCurrency(row.committed)}</td>
                            <td className="mono-number text-right">{formatCurrency(row.available)}</td>
                            <td className="mono-number text-right">{formatPct(row.advance_pct)}</td>
                            <td><TrafficLight status={row.traffic_light === "neutral" ? "yellow" : row.traffic_light} showLabel={false} size="sm" /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
          </DashboardSectionErrorBoundary>
        </TabsContent>

        <TabsContent value="projection">
          <DashboardSectionErrorBoundary>
          <div className="space-y-4" data-testid="projection-view">
            {dashboardData?.meta?.is_informative_missing ? (
              <Card><CardContent className="pt-6 text-sm text-muted-foreground" data-testid="informative-missing-note">Sin datos suficientes para calcular este indicador</CardContent></Card>
            ) : null}

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <KPICard title="Ingreso proyectado remanente" value={projectionKpis.projected_income_remaining ?? null} icon={TrendingUp} />
              <KPICard title="Egreso pendiente remanente" value={projectionKpis.pending_expense_remaining ?? null} icon={Wallet} />
              <KPICard title="Flujo neto proyectado" value={projectionKpis.projected_net_flow ?? null} icon={Landmark} />
              <KPICard title="Saldo final proyectado" value={projectionKpis.projected_final_balance ?? null} icon={CheckCircle} />
              <KPICard title="Necesidad máxima de fondeo" value={projectionKpis.max_funding_need ?? null} icon={AlertTriangle} />
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm">Periodo crítico de caja</CardTitle></CardHeader>
                <CardContent className="text-lg font-semibold" data-testid="critical-period">{projectionKpis.critical_cash_period || "Sin presión"}</CardContent>
              </Card>
            </div>

            {projectionAssumptions.length ? (
              <Card>
                <CardHeader><CardTitle className="font-heading text-base">Escenario base del sistema</CardTitle></CardHeader>
                <CardContent>
                  <ul className="list-disc pl-5 text-sm text-muted-foreground space-y-1" data-testid="projection-assumptions">
                    {projectionAssumptions.map((item, idx) => <li key={`assumption-${idx}`}>{item}</li>)}
                  </ul>
                </CardContent>
              </Card>
            ) : null}

            <Card>
              <CardHeader><CardTitle>Proyección Financiera</CardTitle></CardHeader>
              <CardContent>
                {!projectionRows.length ? <p className="text-muted-foreground" data-testid="projection-empty">{projectionEmptyReason || "Sin datos de proyección para los filtros seleccionados."}</p> : (
                  <div className="overflow-x-auto">
                    <table className="data-table" data-testid="projection-table">
                      <thead>
                        <tr>
                          <th>Periodo</th>
                          <th className="text-right">Saldo inicial</th>
                          <th className="text-right">Ingresos reales</th>
                          <th className="text-right">Ingresos proyectados</th>
                          <th className="text-right">Egresos reales</th>
                          <th className="text-right">Comprometido</th>
                          <th className="text-right">Pendiente por ejercer</th>
                          <th className="text-right">Flujo neto</th>
                          <th className="text-right">Saldo final</th>
                          <th className="text-right">Fondeo requerido</th>
                          <th>Semáforo</th>
                        </tr>
                      </thead>
                      <tbody>
                        {projectionRows.map((row) => (
                          <tr key={row.period_label}>
                            <td>{row.period_label}</td>
                            <td className="mono-number text-right">{formatCurrency(row.opening_balance)}</td>
                            <td className="mono-number text-right">{formatCurrency(row.realized_income)}</td>
                            <td className="mono-number text-right">{formatCurrency(row.projected_income)}</td>
                            <td className="mono-number text-right">{formatCurrency(row.realized_expense)}</td>
                            <td className="mono-number text-right">{formatCurrency(row.committed_expense)}</td>
                            <td className="mono-number text-right">{formatCurrency(row.pending_budget_expense)}</td>
                            <td className="mono-number text-right">{formatCurrency(row.net_flow)}</td>
                            <td className="mono-number text-right">{formatCurrency(row.closing_balance)}</td>
                            <td className="mono-number text-right">{formatCurrency(row.funding_required)}</td>
                            <td><TrafficLight status={row.traffic_light} showLabel={false} size="sm" /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
          </DashboardSectionErrorBoundary>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default Dashboard;
