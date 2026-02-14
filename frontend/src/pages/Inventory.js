import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Plus } from "lucide-react";

const initialForm = {
  company_id: "",
  project_id: "",
  m2_superficie: "",
  m2_construccion: "0",
  lote_edificio: "",
  manzana_departamento: "",
  precio_m2_superficie: "",
  precio_m2_construccion: "0",
  descuento_bonificacion: "0",
};

export default function Inventory() {
  const { api } = useAuth();
  const [items, setItems] = useState([]);
  const [projects, setProjects] = useState([]);
  const [empresas, setEmpresas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(initialForm);

  const filteredProjects = useMemo(() => {
    if (!form.company_id) return projects;
    return projects.filter((p) => p.empresa_id === form.company_id);
  }, [projects, form.company_id]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [inventoryRes, projectsRes, empresasRes] = await Promise.all([
        api().get("/inventory"),
        api().get("/projects"),
        api().get("/empresas"),
      ]);
      setItems(inventoryRes.data || []);
      setProjects(projectsRes.data || []);
      setEmpresas(empresasRes.data || []);
    } catch {
      toast.error("Error al cargar inventario");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const openCreate = () => {
    setEditing(null);
    setForm(initialForm);
    setOpen(true);
  };

  const openEdit = (item) => {
    setEditing(item);
    setForm({
      company_id: item.company_id || "",
      project_id: item.project_id || "",
      m2_superficie: String(item.m2_superficie ?? ""),
      m2_construccion: String(item.m2_construccion ?? "0"),
      lote_edificio: item.lote_edificio || "",
      manzana_departamento: item.manzana_departamento || "",
      precio_m2_superficie: String(item.precio_m2_superficie ?? ""),
      precio_m2_construccion: String(item.precio_m2_construccion ?? "0"),
      descuento_bonificacion: String(item.descuento_bonificacion ?? "0"),
    });
    setOpen(true);
  };

  const buildPayload = () => ({
    ...form,
    m2_superficie: Number(form.m2_superficie || 0),
    m2_construccion: Number(form.m2_construccion || 0),
    precio_m2_superficie: Number(form.precio_m2_superficie || 0),
    precio_m2_construccion: Number(form.precio_m2_construccion || 0),
    descuento_bonificacion: Number(form.descuento_bonificacion || 0),
  });

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!form.company_id || !form.project_id || !form.m2_superficie || !form.precio_m2_superficie || !form.lote_edificio || !form.manzana_departamento) {
      toast.error("Completa los campos obligatorios");
      return;
    }
    try {
      if (editing) {
        await api().put(`/inventory/${editing.id}`, buildPayload());
        toast.success("Ítem actualizado");
      } else {
        await api().post("/inventory", buildPayload());
        toast.success("Ítem creado");
      }
      setOpen(false);
      setForm(initialForm);
      setEditing(null);
      fetchData();
    } catch (error) {
      toast.error(error?.response?.data?.detail?.message || error?.response?.data?.detail || "Error al guardar inventario");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight">Inventarios</h1>
          <p className="text-muted-foreground">Administración de inventario por proyecto</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button onClick={openCreate}><Plus className="h-4 w-4 mr-2" />Nuevo ítem</Button></DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader><DialogTitle>{editing ? "Editar inventario" : "Nuevo inventario"}</DialogTitle></DialogHeader>
            <form onSubmit={onSubmit} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Empresa</Label><Select value={form.company_id} onValueChange={(v) => setForm((p) => ({ ...p, company_id: v, project_id: "" }))}><SelectTrigger><SelectValue placeholder="Seleccionar" /></SelectTrigger><SelectContent>{empresas.map((e) => <SelectItem key={e.id} value={e.id}>{e.nombre}</SelectItem>)}</SelectContent></Select></div>
                <div><Label>Proyecto</Label><Select value={form.project_id} onValueChange={(v) => setForm((p) => ({ ...p, project_id: v }))}><SelectTrigger><SelectValue placeholder="Seleccionar" /></SelectTrigger><SelectContent>{filteredProjects.map((pr) => <SelectItem key={pr.id} value={pr.id}>{pr.code} - {pr.name}</SelectItem>)}</SelectContent></Select></div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label>m2 superficie</Label><Input type="number" step="0.01" value={form.m2_superficie} onChange={(e) => setForm((p) => ({ ...p, m2_superficie: e.target.value }))} /></div>
                <div><Label>m2 construcción</Label><Input type="number" step="0.01" value={form.m2_construccion} onChange={(e) => setForm((p) => ({ ...p, m2_construccion: e.target.value }))} /></div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Lote/Edificio</Label><Input value={form.lote_edificio} onChange={(e) => setForm((p) => ({ ...p, lote_edificio: e.target.value }))} /></div>
                <div><Label>Manzana/Departamento</Label><Input value={form.manzana_departamento} onChange={(e) => setForm((p) => ({ ...p, manzana_departamento: e.target.value }))} /></div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div><Label>Precio m2 superficie</Label><Input type="number" step="0.01" value={form.precio_m2_superficie} onChange={(e) => setForm((p) => ({ ...p, precio_m2_superficie: e.target.value }))} /></div>
                <div><Label>Precio m2 construcción</Label><Input type="number" step="0.01" value={form.precio_m2_construccion} onChange={(e) => setForm((p) => ({ ...p, precio_m2_construccion: e.target.value }))} /></div>
                <div><Label>Descuento</Label><Input type="number" step="0.01" value={form.descuento_bonificacion} onChange={(e) => setForm((p) => ({ ...p, descuento_bonificacion: e.target.value }))} /></div>
              </div>
              <DialogFooter><Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancelar</Button><Button type="submit">Guardar</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader><CardTitle>Listado de inventario</CardTitle></CardHeader>
        <CardContent>
          {loading ? <p className="text-muted-foreground">Cargando...</p> : items.length === 0 ? <p className="text-muted-foreground">No hay inventarios registrados</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-border text-left"><th className="py-2">Clave</th><th>Proyecto</th><th>Precio venta</th><th>Precio total</th><th className="text-right">Acciones</th></tr></thead>
                <tbody>
                  {items.map((it) => (
                    <tr key={it.id} className="border-b border-border/50">
                      <td className="py-2">{it.lote_edificio}-{it.manzana_departamento}</td>
                      <td>{projects.find((p) => p.id === it.project_id)?.code || "-"}</td>
                      <td>{Number(it.precio_venta || 0).toLocaleString("es-MX", { style: "currency", currency: "MXN" })}</td>
                      <td>{Number(it.precio_total || 0).toLocaleString("es-MX", { style: "currency", currency: "MXN" })}</td>
                      <td className="text-right"><Button size="sm" variant="outline" onClick={() => openEdit(it)}>Editar</Button></td>
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
