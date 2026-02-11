import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import KPICard from "../components/KPICard";
import TrafficLight from "../components/TrafficLight";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Wallet, TrendingUp, AlertTriangle, CheckCircle, Building, FileWarning, Clock } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Link } from "react-router-dom";

const Dashboard = () => {
  const { api } = useAuth();
  const [dashboardData, setDashboardData] = useState(null);
  const [empresas, setEmpresas] = useState([]);
  const [projects, setProjects] = useState([]);
  const [filteredProjects, setFilteredProjects] = useState([]);
  const [selectedEmpresa, setSelectedEmpresa] = useState("all");
  const [selectedProject, setSelectedProject] = useState("all");
  const [selectedYear, setSelectedYear] = useState(2025);
  const [selectedMonth, setSelectedMonth] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  const months = [
    { value: 1, label: "Enero" }, { value: 2, label: "Febrero" }, { value: 3, label: "Marzo" },
    { value: 4, label: "Abril" }, { value: 5, label: "Mayo" }, { value: 6, label: "Junio" },
    { value: 7, label: "Julio" }, { value: 8, label: "Agosto" }, { value: 9, label: "Septiembre" },
    { value: 10, label: "Octubre" }, { value: 11, label: "Noviembre" }, { value: 12, label: "Diciembre" },
  ];

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [dashboardRes, empresasRes, projectsRes] = await Promise.all([
        api().get("/reports/dashboard", {
          params: {
            empresa_id: selectedEmpresa !== "all" ? selectedEmpresa : undefined,
            project_id: selectedProject !== "all" ? selectedProject : undefined,
            year: selectedYear,
            month: selectedMonth
          }
        }),
        api().get("/empresas"),
        api().get("/projects")
      ]);
      setDashboardData(dashboardRes.data);
      setEmpresas(empresasRes.data);
      setProjects(projectsRes.data);
    } catch (error) {
      toast.error("Error al cargar datos del dashboard");
    } finally {
      setIsLoading(false);
    }
  }, [api, selectedEmpresa, selectedProject, selectedYear, selectedMonth]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Filter projects when empresa changes
  useEffect(() => {
    if (selectedEmpresa === "all") {
      setFilteredProjects(projects);
    } else {
      setFilteredProjects(projects.filter(p => p.empresa_id === selectedEmpresa));
    }
    setSelectedProject("all");
  }, [selectedEmpresa, projects]);

  const formatCurrency = (num) => {
    return new Intl.NumberFormat("es-MX", {
      style: "currency",
      currency: "MXN",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(num);
  };

  const getBarColor = (percentage) => {
    if (percentage <= 90) return "#10B981";
    if (percentage <= 100) return "#F59E0B";
    return "#EF4444";
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-48 bg-muted rounded" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-32 bg-card rounded-lg border border-border" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">Resumen financiero del período</p>
        </div>
        
        <div className="flex flex-wrap gap-3">
          {/* Empresa filter */}
          <Select value={selectedEmpresa} onValueChange={setSelectedEmpresa}>
            <SelectTrigger className="w-[200px]" data-testid="filter-empresa">
              <SelectValue placeholder="Empresa" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas las empresas</SelectItem>
              {empresas.map((e) => (
                <SelectItem key={e.id} value={e.id}>{e.nombre}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          {/* Project filter (filtered by empresa) */}
          <Select value={selectedProject} onValueChange={setSelectedProject}>
            <SelectTrigger className="w-[180px]" data-testid="filter-project">
              <SelectValue placeholder="Proyecto" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos los proyectos</SelectItem>
              {filteredProjects.map((p) => (
                <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          <Select value={String(selectedMonth)} onValueChange={(v) => setSelectedMonth(Number(v))}>
            <SelectTrigger className="w-[140px]" data-testid="filter-month">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {months.map((m) => (
                <SelectItem key={m.value} value={String(m.value)}>{m.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          <Select value={String(selectedYear)} onValueChange={(v) => setSelectedYear(Number(v))}>
            <SelectTrigger className="w-[100px]" data-testid="filter-year">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[2024, 2025, 2026].map((y) => (
                <SelectItem key={y} value={String(y)}>{y}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <KPICard
          title="Presupuesto"
          value={dashboardData?.totals?.budget || 0}
          icon={Wallet}
          subtitle="Total asignado"
        />
        <KPICard
          title="Ejecutado"
          value={dashboardData?.totals?.real || 0}
          icon={TrendingUp}
          trendValue={dashboardData?.totals?.percentage}
          trend={dashboardData?.totals?.percentage > 100 ? "up" : "neutral"}
          variant="inverse"
        />
        <KPICard
          title="Variación"
          value={dashboardData?.totals?.variation || 0}
          icon={dashboardData?.totals?.variation >= 0 ? CheckCircle : AlertTriangle}
          subtitle={dashboardData?.totals?.variation >= 0 ? "Bajo presupuesto" : "Sobre presupuesto"}
        />
        {/* Pending KPI */}
        <div className="metric-card" data-testid="pending-kpi">
          <div className="flex items-start justify-between mb-3">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Pendiente por Autorizar
            </span>
            <div className="p-2 rounded-md bg-amber-500/10 text-amber-400">
              <Clock className="h-4 w-4" />
            </div>
          </div>
          <p className="text-2xl font-bold font-mono">
            {formatCurrency(dashboardData?.pending?.total_mxn || 0)}
          </p>
          <p className="text-xs text-muted-foreground mt-2">
            {dashboardData?.pending?.count || 0} movimientos pendientes
          </p>
          {(dashboardData?.pending?.count || 0) > 0 && (
            <Link to="/authorizations" className="text-xs text-amber-400 hover:underline mt-1 inline-block">
              Ver autorizaciones →
            </Link>
          )}
        </div>
        <div className="metric-card">
          <div className="flex items-start justify-between mb-3">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Estado General
            </span>
            <div className="p-2 rounded-md bg-primary/10 text-primary">
              <FileWarning className="h-4 w-4" />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <TrafficLight 
              status={dashboardData?.totals?.traffic_light} 
              percentage={dashboardData?.totals?.percentage}
              size="lg"
            />
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            {dashboardData?.pending_authorizations || 0} autorizaciones totales
          </p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* By Partida */}
        <Card>
          <CardHeader>
            <CardTitle className="font-heading text-lg">Avance por Partida</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dashboardData?.by_partida || []} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(240 5% 17%)" />
                  <XAxis type="number" domain={[0, 120]} stroke="hsl(240 5% 65%)" fontSize={12} />
                  <YAxis 
                    dataKey="partida_codigo" 
                    type="category" 
                    width={50} 
                    stroke="hsl(240 5% 65%)" 
                    fontSize={11}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(240 10% 7%)",
                      border: "1px solid hsl(240 5% 17%)",
                      borderRadius: "8px"
                    }}
                    formatter={(value) => [`${value.toFixed(1)}%`, "Avance"]}
                    labelFormatter={(label) => {
                      const p = dashboardData?.by_partida?.find(x => x.partida_codigo === label);
                      return `${label} - ${p?.partida_nombre || ''}`;
                    }}
                  />
                  <Bar dataKey="percentage" radius={[0, 4, 4, 0]}>
                    {(dashboardData?.by_partida || []).map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={getBarColor(entry.percentage)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* By Project */}
        <Card>
          <CardHeader>
            <CardTitle className="font-heading text-lg">Avance por Proyecto</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dashboardData?.by_project || []} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(240 5% 17%)" />
                  <XAxis type="number" domain={[0, 120]} stroke="hsl(240 5% 65%)" fontSize={12} />
                  <YAxis 
                    dataKey="project_code" 
                    type="category" 
                    width={70} 
                    stroke="hsl(240 5% 65%)" 
                    fontSize={11}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(240 10% 7%)",
                      border: "1px solid hsl(240 5% 17%)",
                      borderRadius: "8px"
                    }}
                    formatter={(value) => [`${value.toFixed(1)}%`, "Avance"]}
                    labelFormatter={(label) => `Proyecto: ${label}`}
                  />
                  <Bar dataKey="percentage" radius={[0, 4, 4, 0]}>
                    {(dashboardData?.by_project || []).map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={getBarColor(entry.percentage)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Partidas Table */}
      <Card>
        <CardHeader>
          <CardTitle className="font-heading text-lg flex items-center gap-2">
            <Building className="h-5 w-5" />
            Detalle por Partida
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="data-table" data-testid="partidas-table">
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Partida</th>
                  <th>Grupo</th>
                  <th className="text-right">Presupuesto</th>
                  <th className="text-right">Ejecutado</th>
                  <th className="text-right">Variación</th>
                  <th className="text-right">% Avance</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {(dashboardData?.by_partida || []).map((partida) => (
                  <tr key={partida.partida_codigo}>
                    <td className="font-mono text-sm">{partida.partida_codigo}</td>
                    <td>{partida.partida_nombre}</td>
                    <td className="text-xs text-muted-foreground uppercase">{partida.partida_grupo}</td>
                    <td className="mono-number">{formatCurrency(partida.budget)}</td>
                    <td className="mono-number">{formatCurrency(partida.real)}</td>
                    <td className={`mono-number ${partida.variation >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {formatCurrency(partida.variation)}
                    </td>
                    <td className="mono-number">{partida.percentage.toFixed(1)}%</td>
                    <td>
                      <TrafficLight status={partida.traffic_light} showLabel={false} size="sm" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Dashboard;
