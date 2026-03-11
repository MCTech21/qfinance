import { buildYearOptions } from "../lib/yearRange";
import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import TrafficLight from "../components/TrafficLight";
import { Download, Loader2, FileSpreadsheet, Upload, AlertCircle, CheckCircle, FileText, X } from "lucide-react";
import * as XLSX from "xlsx";
import { saveAs } from "file-saver";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../components/ui/dialog";

const Reports = () => {
  const { api } = useAuth();
  const [partidaDetail, setPartidaDetail] = useState(null);
  const [empresas, setEmpresas] = useState([]);
  const [projects, setProjects] = useState([]);
  const [filteredProjects, setFilteredProjects] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedPartida, setSelectedPartida] = useState(null);
  const [isExporting, setIsExporting] = useState(false);
  
  // Import CSV state
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [isImporting, setIsImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const fileInputRef = useRef(null);
  
  const [filters, setFilters] = useState({
    empresa_id: "all",
    project_id: "all",
    year: new Date().getFullYear(),
    month: 1
  });

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
      const [empresasRes, projectsRes] = await Promise.all([
        api().get("/empresas"),
        api().get("/projects")
      ]);
      setEmpresas(empresasRes.data);
      setProjects(projectsRes.data);
    } catch (error) {
      toast.error("Error al cargar datos");
    } finally {
      setIsLoading(false);
    }
  }, [api]);

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
          empresa_id: filters.empresa_id,
          project_id: filters.project_id,
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

  const exportToExcel = async () => {
    setIsExporting(true);
    
    try {
      // Fetch export data from backend (logs audit)
      const response = await api().get("/reports/export-data", {
        params: {
          empresa_id: filters.empresa_id,
          project_id: filters.project_id,
          year: filters.year,
          month: filters.month
        }
      });
      
      const data = response.data;
      const monthName = months.find(m => m.value === filters.month)?.label || filters.month;
      
      // HOJA 1: RESUMEN (KPIs)
      const resumenData = [
        ["REPORTE FINANCIERO - QFINANCE"],
        [""],
        ["FILTROS APLICADOS"],
        ["Empresa:", data.filtros.empresa],
        ["Proyecto:", data.filtros.proyecto],
        ["Período:", data.periodo],
        ["Generado:", data.generated_at],
        ["Zona horaria:", data.timezone],
        [""],
        ["RESUMEN GENERAL"],
        ["Concepto", "Valor"],
        ["Presupuesto", data.resumen.presupuesto],
        ["Ejecutado", data.resumen.ejecutado],
        ["Variación", data.resumen.variacion],
        ["% Avance", `${data.resumen.porcentaje.toFixed(1)}%`],
        ["Estado", data.resumen.semaforo]
      ];
      
      // HOJA 2: DETALLE POR PARTIDA
      const detalleHeader = ["Código", "Partida", "Grupo", "Presupuesto", "Ejecutado", "Variación", "% Avance", "Semáforo"];
      const detalleRows = (data.detalle_partidas || []).map(p => [
        p.codigo,
        p.nombre,
        p.grupo,
        p.presupuesto,
        p.ejecutado,
        p.variacion,
        `${Number(p.porcentaje || 0).toFixed(1)}%`,
        p.semaforo
      ]);
      
      const detalleData = [
        ["DETALLE POR PARTIDA"],
        ["Período:", data.periodo],
        [""],
        detalleHeader,
        ...detalleRows
      ];
      
      // Create workbook with 2 sheets
      const wb = XLSX.utils.book_new();
      
      // Sheet 1: Resumen
      const wsResumen = XLSX.utils.aoa_to_sheet(resumenData);
      wsResumen['!cols'] = [{ wch: 20 }, { wch: 25 }];
      XLSX.utils.book_append_sheet(wb, wsResumen, "Resumen");
      
      // Sheet 2: Detalle
      const wsDetalle = XLSX.utils.aoa_to_sheet(detalleData);
      wsDetalle['!cols'] = [
        { wch: 10 }, { wch: 35 }, { wch: 15 }, 
        { wch: 15 }, { wch: 15 }, { wch: 15 }, 
        { wch: 12 }, { wch: 10 }
      ];
      XLSX.utils.book_append_sheet(wb, wsDetalle, "Detalle");
      
      // Generate and save file
      const excelBuffer = XLSX.write(wb, { bookType: "xlsx", type: "array" });
      const blob = new Blob([excelBuffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
      saveAs(blob, `QFinance_Reporte_${monthName}_${filters.year}.xlsx`);
      
      toast.success("Reporte exportado correctamente");
    } catch (error) {
      toast.error("Error al exportar reporte");
      console.error(error);
    } finally {
      setIsExporting(false);
    }
  };

  // IMPORT CSV Functions
  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file && file.name.endsWith('.csv')) {
      setImportFile(file);
      setImportResult(null);
    } else {
      toast.error("Solo se aceptan archivos CSV");
    }
  };

  const handleImportCSV = async () => {
    if (!importFile) return;
    
    setIsImporting(true);
    setImportResult(null);
    
    try {
      const formData = new FormData();
      formData.append('file', importFile);
      
      const response = await api().post("/movements/import-csv", formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setImportResult(response.data);
      
      if (response.data.insertadas > 0) {
        toast.success(`${response.data.insertadas} movimientos importados`);
        fetchData(); // Refresh data
      }
      
      if (response.data.rechazadas > 0) {
        toast.warning(`${response.data.rechazadas} filas rechazadas`);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al importar CSV");
      console.error(error);
    } finally {
      setIsImporting(false);
    }
  };

  const downloadTemplateCSV = () => {
    const headers = "fecha,empresa,proyecto,partida,proveedor,moneda,monto,tipo_cambio,referencia,descripcion";
    const example1 = "2025-01-15,Altitud 3,TORRE-A,104,CEMEX,MXN,150000,,FAC-001,Concreto premezclado";
    const example2 = "2025-01-20,Terraviva Desarrollos,PLAZA-M,105,TRANS,USD,5000,17.50,FAC-002,Transporte materiales";
    const csvContent = `${headers}\n${example1}\n${example2}`;
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    saveAs(blob, 'plantilla_import_movimientos.csv');
    toast.success("Plantilla descargada");
  };

  const resetImport = () => {
    setImportFile(null);
    setImportResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
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
          <p className="text-muted-foreground">Centro de descarga e importación de datos financieros</p>
        </div>
        
        <div className="flex gap-2">
          {/* Import CSV Dialog */}
          <Dialog open={showImportDialog} onOpenChange={setShowImportDialog}>
            <DialogTrigger asChild>
              <Button variant="outline" data-testid="import-csv-btn">
                <Upload className="h-4 w-4 mr-2" />
                Importar CSV
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-lg">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  Importar Movimientos desde CSV
                </DialogTitle>
                <DialogDescription>
                  Sube un archivo CSV con los movimientos financieros. Asegúrate de usar el formato correcto.
                </DialogDescription>
              </DialogHeader>
              
              <div className="space-y-4">
                {/* Template download */}
                <Button variant="link" size="sm" className="p-0 h-auto" onClick={downloadTemplateCSV}>
                  <Download className="h-3 w-3 mr-1" />
                  Descargar plantilla CSV de ejemplo
                </Button>
                
                {/* File input */}
                <div className="border-2 border-dashed rounded-lg p-6 text-center">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv"
                    onChange={handleFileSelect}
                    className="hidden"
                    id="csv-file-input"
                    data-testid="csv-file-input"
                  />
                  <label 
                    htmlFor="csv-file-input" 
                    className="cursor-pointer flex flex-col items-center gap-2"
                  >
                    <Upload className="h-8 w-8 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">
                      {importFile ? importFile.name : "Click para seleccionar archivo CSV"}
                    </span>
                  </label>
                </div>
                
                {/* Import button */}
                {importFile && !importResult && (
                  <Button 
                    onClick={handleImportCSV} 
                    disabled={isImporting}
                    className="w-full"
                    data-testid="process-import-btn"
                  >
                    {isImporting ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Procesando...
                      </>
                    ) : (
                      <>
                        <Upload className="h-4 w-4 mr-2" />
                        Procesar Import
                      </>
                    )}
                  </Button>
                )}
                
                {/* Import Results */}
                {importResult && (
                  <div className="space-y-3" data-testid="import-result">
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="p-3 bg-muted rounded-lg">
                        <span className="text-muted-foreground">Total filas</span>
                        <p className="font-bold text-lg">{importResult.total_filas}</p>
                      </div>
                      <div className="p-3 bg-emerald-500/10 rounded-lg">
                        <span className="text-emerald-600">Insertadas</span>
                        <p className="font-bold text-lg text-emerald-600">{importResult.insertadas}</p>
                      </div>
                      <div className="p-3 bg-red-500/10 rounded-lg">
                        <span className="text-red-600">Rechazadas</span>
                        <p className="font-bold text-lg text-red-600">{importResult.rechazadas}</p>
                      </div>
                      <div className="p-3 bg-yellow-500/10 rounded-lg">
                        <span className="text-yellow-600">Duplicadas</span>
                        <p className="font-bold text-lg text-yellow-600">{importResult.duplicadas_omitidas}</p>
                      </div>
                    </div>
                    
                    {/* Errors list */}
                    {importResult.errores && importResult.errores.length > 0 && (
                      <div className="mt-3 max-h-48 overflow-y-auto">
                        <p className="text-sm font-medium mb-2 flex items-center gap-1">
                          <AlertCircle className="h-4 w-4 text-red-500" />
                          Errores encontrados:
                        </p>
                        <div className="space-y-1">
                          {importResult.errores.slice(0, 10).map((err, idx) => (
                            <div key={idx} className="text-xs p-2 bg-red-500/5 rounded border border-red-500/20">
                              <span className="font-medium">Fila {err.fila}:</span>
                              <ul className="ml-3 mt-1">
                                {err.errores.map((e, i) => (
                                  <li key={i} className="text-red-600">
                                    {e.columna}: {e.motivo}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ))}
                          {importResult.errores.length > 10 && (
                            <p className="text-xs text-muted-foreground">
                              ...y {importResult.errores.length - 10} errores más
                            </p>
                          )}
                        </div>
                      </div>
                    )}
                    
                    {importResult.insertadas > 0 && (
                      <div className="flex items-center gap-2 text-sm text-emerald-600">
                        <CheckCircle className="h-4 w-4" />
                        Importación completada exitosamente
                      </div>
                    )}
                    
                    <Button variant="outline" onClick={resetImport} className="w-full">
                      <X className="h-4 w-4 mr-2" />
                      Importar otro archivo
                    </Button>
                  </div>
                )}
                
                {/* Required columns info */}
                <div className="text-xs text-muted-foreground bg-muted p-3 rounded-lg">
                  <p className="font-medium mb-1">Columnas requeridas:</p>
                  <code className="text-[10px]">
                    fecha, empresa, proyecto, partida, proveedor, moneda, monto, tipo_cambio, referencia, descripcion
                  </code>
                  <p className="mt-2 text-[10px]">
                    • USD requiere tipo_cambio • Fecha formato YYYY-MM-DD • Partida por código (ej: 104)
                  </p>
                </div>
              </div>
            </DialogContent>
          </Dialog>
          
          {/* Export Excel Button */}
          <Button onClick={exportToExcel} disabled={isExporting} data-testid="export-excel-btn">
            {isExporting ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Download className="h-4 w-4 mr-2" />
            )}
            Exportar Excel
          </Button>
        </div>
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
                {yearOptions.map(y => (
                  <SelectItem key={y} value={String(y)}>{y}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {isLoading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <Card>
          <CardContent className="pt-6 text-muted-foreground">
            Exporta reportes por empresa/proyecto/mes y consulta detalle por código de partida cuando lo necesites.
          </CardContent>
        </Card>
      )}

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
    </div>
  );
};

export default Reports;
