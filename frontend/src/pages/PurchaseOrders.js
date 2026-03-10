import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { Plus, FileDown, Send, XCircle, Pencil, Trash2, Eye, Loader2 } from "lucide-react";
import ProviderSelect from "../components/ProviderSelect";

const STATUS_LABELS = {
  draft: { label: "Borrador", variant: "secondary" },
  pending_approval: { label: "Pendiente", variant: "outline" },
  approved_for_payment: { label: "Aprobada", variant: "default" },
  rejected: { label: "Rechazada", variant: "destructive" },
  cancelled: { label: "Cancelada", variant: "destructive" },
};

const IVA_OPTIONS = ["0", "8", "16"];

const emptyLine = () => ({
  rowKey: `tmp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  line_no: 1,
  partida_codigo: "",
  description: "",
  qty: "1",
  uom: "",
  price_unit: "",
  discount_pct: "0",
  iva_rate: "16",
  apply_isr_withholding: false,
  isr_withholding_rate: "0",
});

const emptyForm = {
  external_id: "",
  folio: "",
  invoice_folio: "",
  project_id: "",
  provider_id: "",
  vendor_name: "",
  vendor_rfc: "",
  vendor_email: "",
  vendor_phone: "",
  vendor_address: "",
  currency: "MXN",
  exchange_rate: "1",
  order_date: new Date().toISOString().split("T")[0],
  planned_date: "",
  notes: "",
  payment_terms: "",
  apply_iva_withholding: false,
  iva_withholding_rate: "0",
  lines: [emptyLine()],
};

const normalizeAmount = (value) => {
  if (value === null || value === undefined) return 0;
  const raw = String(value).replaceAll(",", "").trim();
  if (!raw) return 0;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : 0;
};

const moneyRound = (n) => Math.round((n + Number.EPSILON) * 100) / 100;

const calcLine = (line) => {
  const qty = normalizeAmount(line.qty);
  const price = normalizeAmount(line.price_unit);
  const discountPct = normalizeAmount(line.discount_pct);
  const iva = normalizeAmount(line.iva_rate);
  const isrRate = line.apply_isr_withholding ? normalizeAmount(line.isr_withholding_rate) : 0;
  const subtotalBeforeDiscount = moneyRound(qty * price);
  const discountAmount = moneyRound(subtotalBeforeDiscount * (discountPct / 100));
  const taxableBase = moneyRound(subtotalBeforeDiscount - discountAmount);
  const ivaAmount = moneyRound(taxableBase * (iva / 100));
  const isrAmount = moneyRound(taxableBase * (isrRate / 100));
  const lineTotal = moneyRound(taxableBase + ivaAmount - isrAmount);
  return { subtotalBeforeDiscount, discountAmount, taxableBase, ivaAmount, isrAmount, lineTotal };
};

const getApiMessage = (error, fallback = "Ocurrió un error") => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  if (detail?.code) return detail.code;
  return fallback;
};

const PurchaseOrders = () => {
  const { api, user } = useAuth();
  const [orders, setOrders] = useState([]);
  const [projects, setProjects] = useState([]);
  const [empresas, setEmpresas] = useState([]);
  const [providers, setProviders] = useState([]);
  const [partidas, setPartidas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openForm, setOpenForm] = useState(false);
  const [openDetail, setOpenDetail] = useState(false);
  const [selected, setSelected] = useState(null);
  const [saving, setSaving] = useState(false);
  const [actingId, setActingId] = useState("");
  const [form, setForm] = useState(emptyForm);
  const [budgetPreview, setBudgetPreview] = useState(null);
  const [budgetPreviewLoading, setBudgetPreviewLoading] = useState(false);
  const [budgetPreviewError, setBudgetPreviewError] = useState("");
  const [filters, setFilters] = useState({
    empresa_id: "all",
    project_id: "all",
    status: "all",
    provider: "",
    search: "",
    date_from: "",
    date_to: "",
  });
  const isAdmin = user?.role === "admin";
  const isDirector = user?.role === "director";

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [ordersRes, projectsRes, empresasRes, providersRes, partidasRes] = await Promise.allSettled([
        api().get("/purchase-orders"),
        api().get("/projects"),
        api().get("/empresas"),
        api().get("/providers"),
        api().get("/catalogo-partidas"),
      ]);
      if (ordersRes.status === "fulfilled") setOrders(ordersRes.value.data || []);
      if (projectsRes.status === "fulfilled") setProjects(projectsRes.value.data || []);
      if (empresasRes.status === "fulfilled") setEmpresas(empresasRes.value.data || []);
      if (providersRes.status === "fulfilled") setProviders(providersRes.value.data || []);
      if (partidasRes.status === "fulfilled") setPartidas(partidasRes.value.data || []);
    } catch {
      toast.error("Error al cargar órdenes de compra");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const egresoPartidas = useMemo(() => partidas.filter((p) => !String(p.codigo || "").startsWith("4")), [partidas]);

  const formTotals = useMemo(() => {
    return form.lines.reduce((acc, line) => {
      const c = calcLine(line);
      acc.subtotal += c.taxableBase;
      acc.tax += c.ivaAmount;
      acc.withholding += c.isrAmount;
      acc.total += c.lineTotal;
      return acc;
    }, { subtotal: 0, tax: 0, withholding: 0, total: 0 });
  }, [form.lines]);


  const lineRequestedAmount = (line) => {
    const c = calcLine(line);
    return Number(c.lineTotal || 0);
  };

  const buildPreviewPayload = useCallback(() => {
    if (!form.project_id || !form.order_date) return null;
    const lines = (form.lines || [])
      .filter((line) => line?.partida_codigo)
      .map((line) => ({
        partida_codigo: line.partida_codigo,
        requested_amount: String(lineRequestedAmount(line).toFixed(2)),
      }));
    if (!lines.length) return null;
    return { project_id: form.project_id, order_date: form.order_date, lines };
  }, [form]);

  useEffect(() => {
    const payload = buildPreviewPayload();
    if (!payload) {
      setBudgetPreview(null);
      setBudgetPreviewError("");
      return;
    }
    const t = setTimeout(async () => {
      setBudgetPreviewLoading(true);
      try {
        const res = await api().post("/budgets/availability/oc-preview", payload);
        setBudgetPreview(res.data || null);
        setBudgetPreviewError("");
      } catch (error) {
        setBudgetPreview(null);
        setBudgetPreviewError(error?.response?.data?.detail?.message || "No se pudo calcular disponibilidad");
      } finally {
        setBudgetPreviewLoading(false);
      }
    }, 350);
    return () => clearTimeout(t);
  }, [api, buildPreviewPayload]);

  const filteredProjects = useMemo(() => {
    if (filters.empresa_id === "all") return projects;
    return projects.filter((p) => p.empresa_id === filters.empresa_id);
  }, [projects, filters.empresa_id]);

  const visibleOrders = useMemo(() => {
    return orders.filter((row) => {
      const project = projects.find((p) => p.id === row.project_id);
      const companyId = row.company_id || project?.empresa_id;
      const orderDate = row.order_date ? new Date(row.order_date) : null;
      if (filters.empresa_id !== "all" && companyId !== filters.empresa_id) return false;
      if (filters.project_id !== "all" && row.project_id !== filters.project_id) return false;
      if (filters.status !== "all" && row.status !== filters.status) return false;
      if (filters.provider && !(row.vendor_name || "").toLowerCase().includes(filters.provider.toLowerCase())) return false;
      if (filters.search) {
        const needle = filters.search.toLowerCase();
      const hay = `${row.folio || row.external_id || ""} ${row.vendor_name || ""}`.toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      if (filters.date_from && orderDate && orderDate < new Date(filters.date_from)) return false;
      if (filters.date_to && orderDate && orderDate > new Date(`${filters.date_to}T23:59:59`)) return false;
      return true;
    });
  }, [orders, projects, filters]);

  const resetForm = () => {
    setForm({ ...emptyForm, lines: [emptyLine()] });
    setBudgetPreview(null);
    setBudgetPreviewError("");
  };

  const openCreate = () => {
    setSelected(null);
    resetForm();
    setOpenForm(true);
  };

  const openEdit = (row) => {
    setSelected(row);
    setForm({
      external_id: row.external_id || "",
      folio: row.folio || row.external_id || "",
      invoice_folio: row.invoice_folio || "",
      project_id: row.project_id || "",
      provider_id: "",
      vendor_name: row.vendor_name || "",
      vendor_rfc: row.vendor_rfc || "",
      vendor_email: row.vendor_email || "",
      vendor_phone: row.vendor_phone || "",
      vendor_address: row.vendor_address || "",
      currency: row.currency || "MXN",
      exchange_rate: row.exchange_rate || "1",
      order_date: row.order_date ? String(row.order_date).slice(0, 10) : new Date().toISOString().slice(0, 10),
      planned_date: row.planned_date ? String(row.planned_date).slice(0, 10) : "",
      notes: row.notes || "",
      payment_terms: row.payment_terms || "",
      apply_iva_withholding: Boolean(row.apply_iva_withholding),
      iva_withholding_rate: String(row.iva_withholding_rate ?? "0"),
      lines: (row.lines || []).map((line, index) => ({
        rowKey: line.id || `tmp-${Date.now()}-${index}`,
        line_no: line.line_no || index + 1,
        partida_codigo: String(line.partida_codigo || ""),
        description: line.description || "",
        qty: String(line.qty ?? "1"),
        uom: line.uom || "",
        price_unit: String(line.price_unit ?? ""),
        discount_pct: String(line.discount_pct ?? "0"),
        iva_rate: String(line.iva_rate ?? "16"),
        apply_isr_withholding: Boolean(line.apply_isr_withholding),
        isr_withholding_rate: String(line.isr_withholding_rate ?? "0"),
      })),
    });
    setOpenForm(true);
  };

  const applyProvider = (providerId) => {
    const provider = providers.find((p) => p.id === providerId);
    setForm((prev) => ({
      ...prev,
      provider_id: providerId,
      vendor_name: provider?.name || prev.vendor_name,
      vendor_rfc: provider?.rfc || prev.vendor_rfc,
      vendor_email: provider?.email || prev.vendor_email,
      vendor_phone: provider?.phone || prev.vendor_phone,
      vendor_address: provider?.address || prev.vendor_address,
    }));
  };

  const changeLine = (rowKey, field, value) => {
    setForm((prev) => ({
      ...prev,
      lines: prev.lines.map((line) => line.rowKey === rowKey ? { ...line, [field]: value } : line),
    }));
  };

  const addLine = () => {
    setForm((prev) => ({
      ...prev,
      lines: [...prev.lines, { ...emptyLine(), line_no: prev.lines.length + 1 }],
    }));
  };

  const removeLine = (rowKey) => {
    setForm((prev) => {
      const next = prev.lines.filter((line) => line.rowKey !== rowKey).map((line, idx) => ({ ...line, line_no: idx + 1 }));
      return { ...prev, lines: next.length ? next : [emptyLine()] };
    });
  };

  const buildPayload = () => ({
    external_id: selected?.id ? (form.external_id || form.folio || null) : null,
    invoice_folio: form.invoice_folio || null,
    project_id: form.project_id,
    vendor_name: form.vendor_name,
    vendor_rfc: form.vendor_rfc || null,
    vendor_email: form.vendor_email || null,
    vendor_phone: form.vendor_phone || null,
    vendor_address: form.vendor_address || null,
    currency: form.currency,
    exchange_rate: form.exchange_rate || "1",
    order_date: form.order_date,
    planned_date: form.planned_date || null,
    notes: form.notes || null,
    payment_terms: form.payment_terms || null,
    lines: form.lines.map((line, idx) => ({
      line_no: idx + 1,
      partida_codigo: line.partida_codigo,
      description: line.description,
      qty: line.qty,
      uom: line.uom || null,
      price_unit: line.price_unit,
      discount_pct: line.discount_pct || "0",
      iva_rate: line.iva_rate,
      apply_isr_withholding: Boolean(line.apply_isr_withholding),
      isr_withholding_rate: line.apply_isr_withholding ? (line.isr_withholding_rate || "0") : "0",
    })),
  });

  const validateForm = () => {
    if (!form.project_id) return "Proyecto es obligatorio";
    if (!form.vendor_name.trim()) return "Proveedor es obligatorio";
    if (!form.lines.length) return "Debe capturar al menos una línea";
    for (const line of form.lines) {
      if (!line.partida_codigo) return "Partida es obligatoria";
      if (String(line.partida_codigo).startsWith("4")) return "Partidas de ingreso (4xx) no permitidas en OC";
      if (!line.description.trim()) return "Descripción de línea es obligatoria";
      if (normalizeAmount(line.qty) <= 0) return "Cantidad debe ser mayor a 0";
      if (normalizeAmount(line.price_unit) < 0) return "Precio unitario no puede ser negativo";
      if (!IVA_OPTIONS.includes(String(line.iva_rate))) return "IVA debe ser 0, 8 o 16";
    }
    return null;
  };

  const saveOrder = async (e) => {
    e.preventDefault();
    const errorText = validateForm();
    if (errorText) {
      toast.error(errorText);
      return;
    }
    setSaving(true);
    try {
      const payload = buildPayload();
      if (selected?.id) {
        await api().put(`/purchase-orders/${selected.id}`, payload);
        toast.success("Orden de compra actualizada");
      } else {
        await api().post("/purchase-orders", payload);
        toast.success("Orden de compra creada");
      }
      setOpenForm(false);
      setSelected(null);
      resetForm();
      fetchData();
    } catch (error) {
      const detail = error?.response?.data?.detail;
      if (detail?.meta?.buckets_exceeded) {
        toast.error(`${detail.message || "Excepción presupuestal"} (${JSON.stringify(detail.meta.buckets_exceeded)})`);
      } else {
        toast.error(getApiMessage(error, "No se pudo guardar OC"));
      }
    } finally {
      setSaving(false);
    }
  };

  const doAction = async (id, action, payload = null, successText = "Acción realizada") => {
    setActingId(id);
    try {
      if (action === "delete") {
        await api().delete(`/purchase-orders/${id}`);
      } else {
        await api().post(`/purchase-orders/${id}/${action}`, payload || {});
      }
      toast.success(successText);
      fetchData();
    } catch (error) {
      const detail = error?.response?.data?.detail;
      if (detail?.meta?.buckets_exceeded) {
        toast.error(`${detail.message || "Excepción presupuestal"} (${JSON.stringify(detail.meta.buckets_exceeded)})`);
      } else {
        toast.error(getApiMessage(error, "No se pudo completar la acción"));
      }
    } finally {
      setActingId("");
    }
  };

  const downloadPdf = async (row) => {
    try {
      const response = await api().get(`/purchase-orders/${row.id}/pdf`, {
        responseType: "blob",
        headers: { Accept: "application/pdf" },
      });
      const blob = new Blob([response.data], { type: "application/pdf" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `OC-${row.external_id || row.id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(getApiMessage(error, "No se pudo descargar PDF"));
    }
  };

  const openView = async (id) => {
    try {
      const res = await api().get(`/purchase-orders/${id}`);
      setSelected(res.data);
      setOpenDetail(true);
    } catch (error) {
      toast.error(getApiMessage(error, "No se pudo cargar el detalle"));
    }
  };

  const roleCanOpenModule = ["admin", "finanzas", "director"].includes(user?.role);

  if (!roleCanOpenModule) {
    return (
      <Card>
        <CardHeader><CardTitle>Órdenes de Compra</CardTitle></CardHeader>
        <CardContent><p className="text-muted-foreground">No tienes permisos para este módulo.</p></CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight">Órdenes de Compra</h1>
          <p className="text-muted-foreground">Captura y workflow de autorización de egresos por OC</p>
        </div>
        <Dialog open={openForm} onOpenChange={(open) => { setOpenForm(open); if (!open) setSelected(null); }}>
          {!isDirector && (
            <DialogTrigger asChild>
              <Button onClick={openCreate}><Plus className="h-4 w-4 mr-2" />Nueva OC</Button>
            </DialogTrigger>
          )}
          <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto">
            <DialogHeader><DialogTitle>{selected ? "Editar OC" : "Nueva OC"}</DialogTitle></DialogHeader>
            <form onSubmit={saveOrder} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div><Label>Folio OC</Label><Input value={selected?.id ? (form.folio || form.external_id || "") : "Se asigna automáticamente al guardar"} readOnly /></div>
                <div><Label>Proyecto</Label><Select value={form.project_id || undefined} onValueChange={(v) => setForm((p) => ({ ...p, project_id: v }))}><SelectTrigger><SelectValue placeholder="Selecciona" /></SelectTrigger><SelectContent>{projects.map((p) => <SelectItem key={p.id} value={p.id}>{p.code} - {p.name}</SelectItem>)}</SelectContent></Select></div>
                <div><Label>Fecha</Label><Input type="date" value={form.order_date} onChange={(e) => setForm((p) => ({ ...p, order_date: e.target.value }))} /></div>
                <div><Label>Fecha programada</Label><Input type="date" value={form.planned_date} onChange={(e) => setForm((p) => ({ ...p, planned_date: e.target.value }))} /></div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div><Label>Proveedor (catálogo)</Label><ProviderSelect apiClient={api} value={form.provider_id} onChange={applyProvider} canCreate={!isDirector} /></div>
                <div><Label>Nombre proveedor</Label><Input value={form.vendor_name} onChange={(e) => setForm((p) => ({ ...p, vendor_name: e.target.value }))} /></div>
                <div><Label>RFC</Label><Input value={form.vendor_rfc} onChange={(e) => setForm((p) => ({ ...p, vendor_rfc: e.target.value }))} /></div>
                <div><Label>Email</Label><Input value={form.vendor_email} onChange={(e) => setForm((p) => ({ ...p, vendor_email: e.target.value }))} /></div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div><Label>Teléfono</Label><Input value={form.vendor_phone} onChange={(e) => setForm((p) => ({ ...p, vendor_phone: e.target.value }))} /></div>
                <div><Label>Moneda</Label><Select value={form.currency} onValueChange={(v) => setForm((p) => ({ ...p, currency: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="MXN">MXN</SelectItem><SelectItem value="USD">USD</SelectItem></SelectContent></Select></div>
                <div><Label>Tipo cambio</Label><Input value={form.exchange_rate} onChange={(e) => setForm((p) => ({ ...p, exchange_rate: e.target.value }))} /></div>
                <div><Label>Condiciones de pago</Label><Input value={form.payment_terms} onChange={(e) => setForm((p) => ({ ...p, payment_terms: e.target.value }))} /></div>
                <div className="flex items-end gap-2"><input id="apply_iva_withholding" type="checkbox" checked={form.apply_iva_withholding} onChange={(e) => setForm((p) => ({ ...p, apply_iva_withholding: e.target.checked }))} /><Label htmlFor="apply_iva_withholding">Retener IVA</Label></div>
                <div><Label>% Retención IVA</Label><Input value={form.iva_withholding_rate} onChange={(e) => setForm((p) => ({ ...p, iva_withholding_rate: e.target.value }))} /></div>
              </div>
              <div><Label>Folio de factura proveedor</Label><Input value={form.invoice_folio} onChange={(e) => setForm((p) => ({ ...p, invoice_folio: e.target.value }))} /></div>
              <div><Label>Dirección proveedor</Label><Input value={form.vendor_address} onChange={(e) => setForm((p) => ({ ...p, vendor_address: e.target.value }))} /></div>
              <div><Label>Notas</Label><Input value={form.notes} onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))} /></div>

              <div className="space-y-2">
                <div className="flex justify-between items-center"><Label>Líneas</Label><Button type="button" size="sm" variant="outline" onClick={addLine}>Agregar línea</Button></div>
                <div className="overflow-x-auto border rounded-md">
                  <table className="w-full text-sm table-fixed">
                    <thead>
                      <tr className="border-b border-border bg-muted/30">
                        <th className="p-2 w-10">#</th><th className="w-24">Partida</th><th className="w-[28%]">Descripción</th><th className="w-16">Cant.</th><th className="w-16">Unidad</th><th className="w-24">P. Unitario</th><th className="w-16">%Desc.</th><th className="w-16">IVA</th><th className="w-20">Ret ISR</th><th className="w-16">%ISR</th><th className="w-24">Total línea</th><th className="w-10"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {form.lines.map((line, idx) => {
                        const lineCalc = calcLine(line);
                        return (
                          <tr key={line.rowKey} className="border-b border-border/50">
                            <td className="p-2 align-top">{idx + 1}</td>
                            <td className="min-w-44">
                              <Select value={line.partida_codigo || undefined} onValueChange={(v) => changeLine(line.rowKey, "partida_codigo", v)}>
                                <SelectTrigger><SelectValue placeholder="Partida" /></SelectTrigger>
                                <SelectContent>
                                  {egresoPartidas.map((p) => <SelectItem key={p.codigo} value={String(p.codigo)}>{p.codigo} - {p.nombre}</SelectItem>)}
                                </SelectContent>
                              </Select>
                            </td>
                            <td className="min-w-56"><Input value={line.description} onChange={(e) => changeLine(line.rowKey, "description", e.target.value)} /></td>
                            <td><Input value={line.qty} onChange={(e) => changeLine(line.rowKey, "qty", e.target.value)} /></td>
                            <td><Input value={line.uom} onChange={(e) => changeLine(line.rowKey, "uom", e.target.value)} /></td>
                            <td><Input value={line.price_unit} onChange={(e) => changeLine(line.rowKey, "price_unit", e.target.value)} /></td>
                            <td><Input value={line.discount_pct} onChange={(e) => changeLine(line.rowKey, "discount_pct", e.target.value)} /></td>
                            <td>
                              <Select value={String(line.iva_rate)} onValueChange={(v) => changeLine(line.rowKey, "iva_rate", v)}>
                                <SelectTrigger><SelectValue /></SelectTrigger>
                                <SelectContent>{IVA_OPTIONS.map((v) => <SelectItem key={v} value={v}>{v}%</SelectItem>)}</SelectContent>
                              </Select>
                            </td>
                            <td><input type="checkbox" checked={line.apply_isr_withholding} onChange={(e) => changeLine(line.rowKey, "apply_isr_withholding", e.target.checked)} /></td>
                            <td><Input value={line.isr_withholding_rate} disabled={!line.apply_isr_withholding} onChange={(e) => changeLine(line.rowKey, "isr_withholding_rate", e.target.value)} /></td>
                            <td className="font-medium text-right pr-2">{lineCalc.lineTotal.toFixed(2)}</td>
                            <td><Button type="button" size="icon" variant="ghost" onClick={() => removeLine(line.rowKey)}><Trash2 className="h-4 w-4" /></Button></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="rounded-lg border border-border/60 p-3 space-y-2">
                <p className="font-medium">Disponibilidad de presupuesto (preview)</p>
                {budgetPreviewLoading && <p className="text-sm text-muted-foreground">Calculando disponibilidad...</p>}
                {budgetPreviewError && <p className="text-sm text-red-400">{budgetPreviewError}</p>}
                {!budgetPreviewLoading && !budgetPreviewError && budgetPreview?.lines?.length > 0 && (
                  <div className="space-y-2 text-sm">
                    {(budgetPreview.lines || []).map((item) => (
                      <div key={item.partida_codigo} className="rounded border border-border/40 p-2">
                        <p className="font-medium">Partida {item.partida_codigo}</p>
                        <p>Total presupuesto: <span className="font-mono">{Number(item.budget_total || 0).toFixed(2)}</span></p>
                        <p>Ejecutado: <span className="font-mono">{Number(item.executed_total || 0).toFixed(2)}</span></p>
                        <p>Disponible actual: <span className="font-mono">{Number(item.remaining_total_current || 0).toFixed(2)}</span></p>
                        <p>Monto proyectado línea(s): <span className="font-mono">{Number(item.requested_amount || 0).toFixed(2)}</span></p>
                        <p>Restante proyectado: <span className="font-mono font-semibold">{Number(item.projected_remaining_total || 0).toFixed(2)}</span></p>
                      </div>
                    ))}
                    <div className="rounded border border-emerald-500/20 bg-emerald-500/10 p-2">
                      <p>Resumen OC - disponible actual: <span className="font-mono">{Number(budgetPreview?.summary?.disponible_actual || 0).toFixed(2)}</span></p>
                      <p>Resumen OC - monto solicitado: <span className="font-mono">{Number(budgetPreview?.summary?.monto_solicitado || 0).toFixed(2)}</span></p>
                      <p>Resumen OC - restante proyectado: <span className="font-mono font-semibold">{Number(budgetPreview?.summary?.restante_proyectado || 0).toFixed(2)}</span></p>
                    </div>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-md border p-2"><p className="text-xs text-muted-foreground">Subtotal base</p><p className="font-semibold">{formTotals.subtotal.toFixed(2)}</p></div>
                <div className="rounded-md border p-2"><p className="text-xs text-muted-foreground">IVA total</p><p className="font-semibold">{formTotals.tax.toFixed(2)}</p></div>
                <div className="rounded-md border p-2"><p className="text-xs text-muted-foreground">Ret ISR</p><p className="font-semibold">{formTotals.withholding.toFixed(2)}</p></div>
                <div className="rounded-md border p-2"><p className="text-xs text-muted-foreground">Total OC</p><p className="font-semibold">{formTotals.total.toFixed(2)}</p></div>
              </div>

              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setOpenForm(false)}>Cancelar</Button>
                <Button type="submit" disabled={saving}>{saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}Guardar</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader><CardTitle>Filtros</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <Select value={filters.empresa_id} onValueChange={(v) => setFilters((p) => ({ ...p, empresa_id: v, project_id: "all" }))}><SelectTrigger><SelectValue placeholder="Empresa" /></SelectTrigger><SelectContent><SelectItem value="all">Todas</SelectItem>{empresas.map((e) => <SelectItem key={e.id} value={e.id}>{e.nombre}</SelectItem>)}</SelectContent></Select>
            <Select value={filters.project_id} onValueChange={(v) => setFilters((p) => ({ ...p, project_id: v }))}><SelectTrigger><SelectValue placeholder="Proyecto" /></SelectTrigger><SelectContent><SelectItem value="all">Todos</SelectItem>{filteredProjects.map((p) => <SelectItem key={p.id} value={p.id}>{p.code} - {p.name}</SelectItem>)}</SelectContent></Select>
            <Select value={filters.status} onValueChange={(v) => setFilters((p) => ({ ...p, status: v }))}><SelectTrigger><SelectValue placeholder="Estatus" /></SelectTrigger><SelectContent><SelectItem value="all">Todos</SelectItem>{Object.keys(STATUS_LABELS).map((status) => <SelectItem key={status} value={status}>{STATUS_LABELS[status].label}</SelectItem>)}</SelectContent></Select>
            <Input placeholder="Proveedor" value={filters.provider} onChange={(e) => setFilters((p) => ({ ...p, provider: e.target.value }))} />
            <Input placeholder="Folio / búsqueda" value={filters.search} onChange={(e) => setFilters((p) => ({ ...p, search: e.target.value }))} />
            <Input type="date" value={filters.date_from} onChange={(e) => setFilters((p) => ({ ...p, date_from: e.target.value }))} />
            <Input type="date" value={filters.date_to} onChange={(e) => setFilters((p) => ({ ...p, date_to: e.target.value }))} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Listado de OC</CardTitle></CardHeader>
        <CardContent>
          {loading ? <p className="text-muted-foreground">Cargando...</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm table-fixed">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="py-2">Folio</th><th>Fecha</th><th>Empresa</th><th>Proyecto</th><th>Proveedor</th><th>Estatus</th><th>Gate</th><th>Subtotal</th><th>IVA</th><th>ISR</th><th>Total</th><th>Creador</th><th className="text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleOrders.map((row) => {
                    const status = STATUS_LABELS[row.status] || { label: row.status || "N/A", variant: "secondary" };
                    const project = projects.find((p) => p.id === row.project_id);
                    const company = empresas.find((e) => e.id === (row.company_id || project?.empresa_id));
                    const isDraft = row.status === "draft" || row.status === "rejected";
                    const isPending = row.status === "pending_approval";
                    const isApproved = row.status === "approved_for_payment";
                    const disabled = actingId === row.id;
                    return (
                      <tr key={row.id} className="border-b border-border/50">
                        <td className="py-2 font-medium">{row.folio || row.external_id || "-"}</td>
                        <td>{row.order_date ? new Date(row.order_date).toLocaleDateString("es-MX") : "-"}</td>
                        <td>{company?.nombre || "-"}</td>
                        <td>{project ? `${project.code} - ${project.name}` : row.project_id}</td>
                        <td>{row.vendor_name || "-"}</td>
                        <td><Badge variant={status.variant}>{status.label}</Badge></td>
                        <td>{row.budget_gate_status || "-"}</td>
                        <td>{Number(row.subtotal_tax_base || 0).toFixed(2)}</td>
                        <td>{Number(row.tax_total || 0).toFixed(2)}</td>
                        <td>{Number(row.withholding_isr_total || 0).toFixed(2)}</td>
                        <td className="font-semibold">{Number(row.total || 0).toFixed(2)}</td>
                        <td>{row.created_by_user_id || "-"}</td>
                        <td className="text-right">
                          <div className="flex justify-end gap-1 flex-wrap">
                            <Button size="icon" variant="outline" onClick={() => openView(row.id)} title="Ver"><Eye className="h-4 w-4" /></Button>
                            {isDraft && !isDirector && <Button size="icon" variant="outline" onClick={() => openEdit(row)} title="Editar"><Pencil className="h-4 w-4" /></Button>}
                            {isDraft && !isDirector && <Button size="icon" variant="outline" disabled={disabled} onClick={() => doAction(row.id, "submit", null, "OC enviada a autorización")} title="Enviar"><Send className="h-4 w-4" /></Button>}

                            {isPending && isAdmin && <Button size="icon" variant="outline" disabled={disabled} onClick={() => { const reason = window.prompt("Motivo de rechazo"); if (reason) doAction(row.id, "reject", { reason }, "OC rechazada"); }} title="Rechazar"><XCircle className="h-4 w-4" /></Button>}
                            {isDraft && !isDirector && <Button size="icon" variant="destructive" disabled={disabled} onClick={() => doAction(row.id, "delete", null, "OC cancelada")} title="Eliminar"><Trash2 className="h-4 w-4" /></Button>}
                            {(isApproved || isPending || isDraft || row.status === "rejected") && <Button size="icon" variant="outline" onClick={() => downloadPdf(row)} title="PDF"><FileDown className="h-4 w-4" /></Button>}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {!visibleOrders.length && (
                    <tr><td colSpan={13} className="py-8 text-center text-muted-foreground">Sin registros</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={openDetail} onOpenChange={setOpenDetail}>
        <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Detalle OC</DialogTitle></DialogHeader>
          {!selected ? <p className="text-muted-foreground">Sin datos</p> : (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div><p className="text-muted-foreground">Folio</p><p className="font-medium">{selected.folio || selected.external_id}</p></div>
                <div><p className="text-muted-foreground">Estado</p><p>{selected.status}</p></div>
                <div><p className="text-muted-foreground">Budget Gate</p><p>{selected.budget_gate_status || "-"}</p></div>
                <div><p className="text-muted-foreground">Posting</p><p>{selected.posting_status || "-"}</p></div>
              </div>
              <div><p className="text-muted-foreground">Folio factura proveedor</p><p>{selected.invoice_folio || "-"}</p></div>
              <div><p className="text-muted-foreground">Proveedor</p><p>{selected.vendor_name}</p></div>
              <div className="overflow-x-auto border rounded-md">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-border"><th className="p-2 text-left">#</th><th className="text-left">Partida</th><th className="text-left">Descripción</th><th className="text-right">Total línea</th></tr></thead>
                  <tbody>
                    {(selected.lines || []).map((line) => (
                      <tr key={line.id || `${line.line_no}-${line.partida_codigo}`} className="border-b border-border/50"><td className="p-2 align-top">{line.line_no}</td><td>{line.partida_codigo}</td><td>{line.description}</td><td className="text-right pr-2">{Number(line.line_total || 0).toFixed(2)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          <DialogFooter><Button variant="outline" onClick={() => setOpenDetail(false)}>Cerrar</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PurchaseOrders;
