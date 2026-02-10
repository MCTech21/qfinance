import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import TrafficLight from "../components/TrafficLight";
import { Download, Loader2, FileSpreadsheet } from "lucide-react";
import * as XLSX from "xlsx";
import { saveAs } from "file-saver";

const Reports = () => {
  const { api } = useAuth();
  const [dashboardData, setDashboardData] = useState(null);
  const [partidaDetail, setPartidaDetail] = useState(null);
  const [empresas, setEmpresas] = useState([]);
  const [projects, setProjects] = useState([]);
  const [filteredProjects, setFilteredProjects] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedPartida, setSelectedPartida] = useState(null);
  
  const [filters, setFilters] = useState({
    empresa_id: "all",
    project_id: "all",
    year: 2025,
    month: 1
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
      const [dashboardRes, empresasRes, projectsRes] = await Promise.all([
        api().get("/reports/dashboard", {
          params: {
            empresa_id: filters.empresa_id !== "all" ? filters.empresa_id : undefined,
            project_id: filters.project_id !== "all" ? filters.project_id : undefined,
            year: filters.year,
            month: filters.month
          }
        }),
        api().get("/empresas"),
        api().get("/projects")
      ]);
      setDashboardData(dashboardRes.data);
      setEmpresas(empresasRes.data);
      setProjects(projectsRes.data);
    } catch (error) {
      toast.error("Error al cargar datos");
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

  const fetchPartidaDetail = async (partidaCodigo) => {
    try {
      const response = await api().get(`/reports/partida-detail/${partidaCodigo}`, {
        params: {
          empresa_id: filters.empresa_id !== "all" ? filters.empresa_id : undefined,
          project_id: filters.project_id !== "all" ? filters.project_id : undefined,
          year: filters.year,
          month: filters.month
        }
      });
      setPartidaDetail(response.data);
      setSelectedPartida(partidaCodigo);
    } catch (error) {
      toast.error("Error al cargar detalle");
    }
  };

  const formatCurrency = (num) => {
    return new Intl.NumberFormat("es-MX", {
      style: "currency",
      currency: "MXN",
      minimumFractionDigits: 0,
    }).format(num);
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString("es-MX", {
      day: "2-digit",
      month: "short",
      year: "numeric"
    });
  };

  const exportToExcel = () => {
    if (!dashboardData) return;
    
    const monthName = months.find(m => m.value === filters.month)?.label || filters.month;
    
    const summaryData = [
      ["REPORTE FINANCIERO", "", "", ""],
      ["Período:", `${monthName} ${filters.year}`, "", ""],
      ["", "", "", ""],
      ["RESUMEN GENERAL", "", "", ""],
      ["Presupuesto", formatCurrency(dashboardData.totals.budget), "", ""],
      ["Ejecutado", formatCurrency(dashboardData.totals.real), "", ""],
      ["Variación", formatCurrency(dashboardData.totals.variation), "", ""],
      ["% Avance", `${dashboardData.totals.percentage.toFixed(1)}%`, "", ""],
      ["", "", "", ""],
      ["DETALLE POR PARTIDA", "", "", "", "", "", "", ""],
      ["Código", "Partida", "Grupo", "Presupuesto", "Ejecutado", "Variación", "% Avance", "Estado"],
      ...dashboardData.by_partida.map(p => [
        p.partida_codigo,
        p.partida_nombre,
        p.partida_grupo,
        p.budget,
        p.real,
        p.variation,
        `${p.percentage.toFixed(1)}%`,
        p.traffic_light === "green" ? "Normal" : p.traffic_light === "yellow" ? "Alerta" : "Exceso"
      ])
    ];
    
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet(summaryData);
    ws['!cols'] = [{ wch: 12 }, { wch: 35 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 12 }, { wch: 10 }];
    XLSX.utils.book_append_sheet(wb, ws, "Reporte");
    
    const excelBuffer = XLSX.write(wb, { bookType: "xlsx", type: "array" });
    const data = new Blob([excelBuffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    saveAs(data, `Reporte_Financiero_${monthName}_${filters.year}.xlsx`);
    
    toast.success("Reporte exportado");
  };

  const exportDetailToExcel = () => {
    if (!partidaDetail) return;
    
    const monthName = months.find(m => m.value === filters.month)?.label || filters.month;
    
    const detailData = [
      ["DETALLE DE PARTIDA", "", "", "", "", ""],
      ["Código:", partidaDetail.partida.codigo, "", "", "", ""],
      ["Partida:", partidaDetail.partida.nombre, "", "", "", ""],
      ["Grupo:", partidaDetail.partida.grupo, "", "", "", ""],
      ["Período:", `${monthName} ${filters.year}`, "", "", "", ""],
      ["Presupuesto:", formatCurrency(partidaDetail.budget), "", "", "", ""],
      ["Ejecutado:", formatCurrency(partidaDetail.real), "", "", "", ""],
      ["Variación:", formatCurrency(partidaDetail.variation), "", "", "", ""],
      ["% Avance:", `${partidaDetail.percentage.toFixed(1)}%`, "", "", "", ""],
      ["", "", "", "", "", ""],
      ["MOVIMIENTOS", "", "", "", "", ""],
      ["Fecha", "Proyecto", "Proveedor", "Referencia", "Monto MXN", "Descripción"],
      ...partidaDetail.movements.map(m => [
        formatDate(m.date),
        m.project_name,
        m.provider_name,
        m.reference,
        m.amount_mxn,
        m.description || ""
      ])
    ];
    
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet(detailData);
    ws['!cols'] = [{ wch: 15 }, { wch: 25 }, { wch: 25 }, { wch: 15 }, { wch: 15 }, { wch: 30 }];
    XLSX.utils.book_append_sheet(wb, ws, "Detalle");
    
    const excelBuffer = XLSX.write(wb, { bookType: "xlsx", type: "array" });
    const data = new Blob([excelBuffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    saveAs(data, `Detalle_${partidaDetail.partida.codigo}_${monthName}_${filters.year}.xlsx`);
    
    toast.success("Detalle exportado");
  };

  return (
    <div className="space-y-6" data-testid="reports-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight">Reportes</h1>
          <p className="text-muted-foreground">Análisis y exportación de datos financieros</p>
        </div>
        
        <Button onClick={exportToExcel} disabled={!dashboardData} data-testid="export-excel-btn">
          <Download className="h-4 w-4 mr-2" />
          Exportar Excel
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-4">
            {/* Empresa filter */}
            <Select
              value={filters.empresa_id}
              onValueChange={(v) => setFilters(prev => ({ ...prev, empresa_id: v, project_id: "all" }))}
            >
              <SelectTrigger className="w-[200px]" data-testid="filter-empresa">
                <SelectValue placeholder="Empresa" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas las empresas</SelectItem>
                {empresas.map(e => (
                  <SelectItem key={e.id} value={e.id}>{e.nombre}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            {/* Project filter */}
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

      {/* Summary */}
      {isLoading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : dashboardData && (
        <>
          {/* KPIs Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="metric-card">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Presupuesto</span>
              <p className="text-2xl font-bold font-mono mt-2">{formatCurrency(dashboardData.totals.budget)}</p>
            </div>
            <div className="metric-card">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Ejecutado</span>
              <p className="text-2xl font-bold font-mono mt-2">{formatCurrency(dashboardData.totals.real)}</p>
            </div>
            <div className="metric-card">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Variación</span>
              <p className={`text-2xl font-bold font-mono mt-2 ${dashboardData.totals.variation >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {formatCurrency(dashboardData.totals.variation)}
              </p>
            </div>
            <div className="metric-card">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Estado</span>
              <div className="mt-2">
                <TrafficLight 
                  status={dashboardData.totals.traffic_light} 
                  percentage={dashboardData.totals.percentage}
                  size="lg"
                />
              </div>
            </div>
          </div>

          {/* Partidas Table */}
          <Card>
            <CardHeader>
              <CardTitle className="font-heading text-lg">Detalle por Partida</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="data-table" data-testid="partidas-report-table">
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
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboardData.by_partida.map(partida => (
                      <tr 
                        key={partida.partida_codigo}
                        className={selectedPartida === partida.partida_codigo ? "bg-primary/5" : ""}
                      >
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
                        <td>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => fetchPartidaDetail(partida.partida_codigo)}
                            data-testid={`view-detail-${partida.partida_codigo}`}
                          >
                            Ver detalle
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Partida Detail */}
          {partidaDetail && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="font-heading text-lg flex items-center gap-2">
                  <FileSpreadsheet className="h-5 w-5" />
                  Movimientos: {partidaDetail.partida.codigo} - {partidaDetail.partida.nombre}
                </CardTitle>
                <Button variant="outline" size="sm" onClick={exportDetailToExcel} data-testid="export-detail-btn">
                  <Download className="h-4 w-4 mr-2" />
                  Exportar
                </Button>
              </CardHeader>
              <CardContent>
                <div className="mb-4 p-4 bg-muted rounded-lg grid grid-cols-2 md:grid-cols-5 gap-4">
                  <div>
                    <span className="text-xs text-muted-foreground">Grupo</span>
                    <p className="font-medium text-sm uppercase">{partidaDetail.partida.grupo}</p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">Presupuesto</span>
                    <p className="font-mono font-bold">{formatCurrency(partidaDetail.budget)}</p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">Ejecutado</span>
                    <p className="font-mono font-bold">{formatCurrency(partidaDetail.real)}</p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">Variación</span>
                    <p className={`font-mono font-bold ${partidaDetail.variation >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {formatCurrency(partidaDetail.variation)}
                    </p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">Estado</span>
                    <div className="mt-1">
                      <TrafficLight status={partidaDetail.traffic_light} percentage={partidaDetail.percentage} />
                    </div>
                  </div>
                </div>
                
                {partidaDetail.movements.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No hay movimientos en este período
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="data-table" data-testid="movements-detail-table">
                      <thead>
                        <tr>
                          <th>Fecha</th>
                          <th>Proyecto</th>
                          <th>Proveedor</th>
                          <th>Referencia</th>
                          <th className="text-right">Monto MXN</th>
                          <th>Descripción</th>
                        </tr>
                      </thead>
                      <tbody>
                        {partidaDetail.movements.map(mov => (
                          <tr key={mov.id}>
                            <td className="font-mono text-sm">{formatDate(mov.date)}</td>
                            <td>{mov.project_name}</td>
                            <td>{mov.provider_name}</td>
                            <td className="font-mono text-sm">{mov.reference}</td>
                            <td className="mono-number">{formatCurrency(mov.amount_mxn)}</td>
                            <td className="text-muted-foreground text-sm max-w-[200px] truncate">
                              {mov.description || "-"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
};

export default Reports;
