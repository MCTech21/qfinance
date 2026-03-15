import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { FileSpreadsheet } from "lucide-react";
import * as XLSX from "xlsx";
import { saveAs } from "file-saver";

const money = (n) => Number(n || 0).toLocaleString("es-MX", { style: "currency", currency: "MXN" });

const formatDate = (isoStr) => {
  if (!isoStr) return "-";
  const d = new Date(isoStr);
  if (Number.isNaN(d.getTime())) return "-";
  return `${d.toLocaleDateString("es-MX")} ${d.toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" })}`;
};

const statusBadge = (status) => {
  if (status === "approved_for_payment") return <Badge className="bg-green-600">Aprobada Total</Badge>;
  if (status === "partially_approved") return <Badge className="bg-yellow-600 text-black">Aprobada Parcial</Badge>;
  return <Badge variant="outline">{status || "-"}</Badge>;
};

const postingBadge = (posting) => {
  if (posting === "posted") return <Badge className="bg-green-600">Posted</Badge>;
  if (posting === "partially_posted") return <Badge className="bg-yellow-600 text-black">Parcial</Badge>;
  return <Badge variant="outline">No Posted</Badge>;
};

export default function PurchaseOrdersHistory() {
  const { api } = useAuth();
  const [history, setHistory] = useState([]);
  const [projects, setProjects] = useState([]);
  const [empresas, setEmpresas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    company_id: "all",
    project_id: "all",
    status_filter: "all",
    from_date: "",
    to_date: "",
  });

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filters.company_id !== "all") params.company_id = filters.company_id;
      if (filters.project_id !== "all") params.project_id = filters.project_id;
      if (filters.status_filter !== "all") params.status_filter = filters.status_filter;
      if (filters.from_date) params.from_date = filters.from_date;
      if (filters.to_date) params.to_date = filters.to_date;

      const res = await api().get("/purchase-orders/approved-history", { params });
      setHistory(res.data || []);
    } catch {
      toast.error("Error al cargar historial de OC aprobadas");
    } finally {
      setLoading(false);
    }
  }, [api, filters]);

  useEffect(() => {
    const loadCatalogs = async () => {
      const [projectsRes, empresasRes] = await Promise.allSettled([api().get("/projects"), api().get("/empresas")]);
      if (projectsRes.status === "fulfilled") setProjects(projectsRes.value.data || []);
      else setProjects([]);
      if (empresasRes.status === "fulfilled") setEmpresas(empresasRes.value.data || []);
      else setEmpresas([]);
    };
    loadCatalogs();
  }, [api]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const filteredProjects = useMemo(() => {
    if (filters.company_id === "all") return projects;
    return projects.filter((p) => p.empresa_id === filters.company_id);
  }, [projects, filters.company_id]);

  const exportToExcel = () => {
    const rows = history.map((po) => ({
      "Folio OC": po.folio || po.external_id || "-",
      Proveedor: po.vendor_name || "-",
      "RFC Proveedor": po.vendor_rfc || "-",
      Empresa: po.empresa_nombre || "-",
      Proyecto: po.project_code ? `${po.project_code} - ${po.project_name || ""}` : "-",
      "Monto Total": Number(po.total || 0),
      "Monto Aprobado": Number(po.approved_amount_total || 0),
      "Monto Pendiente": Number(po.pending_amount || 0),
      Estado: po.status === "approved_for_payment" ? "Aprobada Total" : po.status === "partially_approved" ? "Aprobada Parcial" : (po.status || "-"),
      Posting: po.posting_status === "posted" ? "Posted" : po.posting_status === "partially_posted" ? "Parcial" : "No Posted",
      "Aprobado Por": po.approved_by_name || po.approved_by_email || "-",
      "Fecha Aprobación": formatDate(po.approved_at),
      "Fecha Orden": po.order_date ? new Date(po.order_date).toLocaleDateString("es-MX") : "-",
      Notas: po.notes || "-",
    }));

    const ws = XLSX.utils.json_to_sheet(rows);
    if (ws["!ref"]) {
      const range = XLSX.utils.decode_range(ws["!ref"]);
      for (let row = range.s.r + 1; row <= range.e.r; row += 1) {
        ["F", "G", "H"].forEach((col) => {
          const cell = ws[`${col}${row + 1}`];
          if (cell && typeof cell.v === "number") {
            cell.z = '"$"#,##0.00';
          }
        });
      }
    }

    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Historial OC Aprobadas");
    const today = new Date().toISOString().split("T")[0];
    const buffer = XLSX.write(wb, { type: "array", bookType: "xlsx" });
    saveAs(
      new Blob([buffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }),
      `historial_oc_aprobadas_${today}.xlsx`,
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight">Historial de OC Aprobadas</h1>
          <p className="text-muted-foreground">Registro de todas las órdenes de compra que han sido aprobadas</p>
        </div>
        <Button variant="outline" onClick={exportToExcel} disabled={history.length === 0}>
          <FileSpreadsheet className="h-4 w-4 mr-2" />
          Exportar Excel
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Filtros</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div>
            <Label>Empresa</Label>
            <Select value={filters.company_id} onValueChange={(v) => setFilters((p) => ({ ...p, company_id: v, project_id: "all" }))}>
              <SelectTrigger>
                <SelectValue placeholder="Todas" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas</SelectItem>
                {empresas.map((e) => (
                  <SelectItem key={e.id} value={e.id}>{e.nombre}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label>Proyecto</Label>
            <Select value={filters.project_id} onValueChange={(v) => setFilters((p) => ({ ...p, project_id: v }))}>
              <SelectTrigger>
                <SelectValue placeholder="Todos" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                {filteredProjects.map((pr) => (
                  <SelectItem key={pr.id} value={pr.id}>{pr.code} - {pr.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label>Estado</Label>
            <Select value={filters.status_filter} onValueChange={(v) => setFilters((p) => ({ ...p, status_filter: v }))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas</SelectItem>
                <SelectItem value="approved">Aprobadas Totalmente</SelectItem>
                <SelectItem value="partially_approved">Aprobadas Parcialmente</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label>Desde</Label>
            <Input type="date" value={filters.from_date} onChange={(e) => setFilters((p) => ({ ...p, from_date: e.target.value }))} />
          </div>

          <div>
            <Label>Hasta</Label>
            <Input type="date" value={filters.to_date} onChange={(e) => setFilters((p) => ({ ...p, to_date: e.target.value }))} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Historial ({history.length} registros)</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Cargando...</p>
          ) : history.length === 0 ? (
            <p className="text-muted-foreground">No hay OC aprobadas en el período seleccionado</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="py-2">Folio</th>
                    <th>Proveedor</th>
                    <th>RFC</th>
                    <th>Proyecto</th>
                    <th>Empresa</th>
                    <th>Total</th>
                    <th>Aprobado</th>
                    <th>Pendiente</th>
                    <th>Estado</th>
                    <th>Posting</th>
                    <th>Aprobado Por</th>
                    <th>Fecha Aprobación</th>
                    <th>Fecha Orden</th>
                    <th>Notas</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((po) => (
                    <tr key={po.id} className="border-b border-border/50">
                      <td className="py-2">{po.folio || po.external_id || "-"}</td>
                      <td>{po.vendor_name || "-"}</td>
                      <td>{po.vendor_rfc || "-"}</td>
                      <td>{po.project_code ? `${po.project_code} - ${po.project_name || ""}` : "-"}</td>
                      <td>{po.empresa_nombre || "-"}</td>
                      <td>{money(po.total)}</td>
                      <td>{money(po.approved_amount_total)}</td>
                      <td>{money(po.pending_amount)}</td>
                      <td>{statusBadge(po.status)}</td>
                      <td>{postingBadge(po.posting_status)}</td>
                      <td className="max-w-[220px] truncate">{po.approved_by_name || po.approved_by_email || "-"}</td>
                      <td>{formatDate(po.approved_at)}</td>
                      <td>{po.order_date ? new Date(po.order_date).toLocaleDateString("es-MX") : "-"}</td>
                      <td className="max-w-[320px] truncate">{po.notes || "-"}</td>
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
}
