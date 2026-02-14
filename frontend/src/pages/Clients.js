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
  nombre: "",
  telefono: "",
  domicilio: "",
  inventory_item_id: "",
};

export default function Clients() {
  const { api } = useAuth();
  const [clients, setClients] = useState([]);
  const [projects, setProjects] = useState([]);
  const [empresas, setEmpresas] = useState([]);
  const [inventoryItems, setInventoryItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(initialForm);

  const filteredProjects = useMemo(() => {
    if (!form.company_id) return projects;
    return projects.filter((p) => p.empresa_id === form.company_id);
  }, [projects, form.company_id]);

  const companyInventory = useMemo(() => {
    if (!form.company_id) return inventoryItems;
    return inventoryItems.filter((it) => it.company_id === form.company_id && (!form.project_id || it.project_id === form.project_id));
  }, [inventoryItems, form.company_id, form.project_id]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [clientsRes, projectsRes, empresasRes, inventoryRes] = await Promise.all([
        api().get("/clients"),
        api().get("/projects"),
        api().get("/empresas"),
        api().get("/inventory"),
      ]);
      setClients(clientsRes.data || []);
      setProjects(projectsRes.data || []);
      setEmpresas(empresasRes.data || []);
      setInventoryItems(inventoryRes.data || []);
    } catch {
      toast.error("Error al cargar clientes");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const reset = () => {
    setEditing(null);
    setForm(initialForm);
  };

  const openCreate = () => {
    reset();
    setOpen(true);
  };

  const openEdit = (client) => {
    setEditing(client);
    setForm({
      company_id: client.company_id || "",
      project_id: client.project_id || "",
      nombre: client.nombre || "",
      telefono: client.telefono || "",
      domicilio: client.domicilio || "",
      inventory_item_id: client.inventory_item_id || "",
    });
    setOpen(true);
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!form.nombre.trim()) {
      toast.error("Nombre es obligatorio");
      return;
    }
    if (!form.company_id || !form.project_id) {
      toast.error("Empresa y proyecto son obligatorios");
      return;
    }

    const payload = {
      ...form,
      inventory_item_id: form.inventory_item_id || null,
      nombre: form.nombre,
    };

    try {
      if (editing) {
        await api().put(`/clients/${editing.id}`, {
          nombre: payload.nombre,
          telefono: payload.telefono,
          domicilio: payload.domicilio,
          inventory_item_id: payload.inventory_item_id,
        });
        toast.success("Cliente actualizado");
      } else {
        await api().post("/clients", payload);
        toast.success("Cliente creado");
      }
      setOpen(false);
      reset();
      fetchData();
    } catch (error) {
      toast.error(error?.response?.data?.detail?.message || error?.response?.data?.detail || "Error al guardar cliente");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight">Clientes</h1>
          <p className="text-muted-foreground">Administración de clientes</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button onClick={openCreate}><Plus className="h-4 w-4 mr-2" />Nuevo cliente</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>{editing ? "Editar cliente" : "Nuevo cliente"}</DialogTitle></DialogHeader>
            <form onSubmit={onSubmit} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1"><Label>Empresa</Label>
                  <Select value={form.company_id} onValueChange={(v) => setForm((p) => ({ ...p, company_id: v, project_id: "", inventory_item_id: "" }))}>
                    <SelectTrigger><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                    <SelectContent>{empresas.map((e) => <SelectItem key={e.id} value={e.id}>{e.nombre}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="space-y-1"><Label>Proyecto</Label>
                  <Select value={form.project_id} onValueChange={(v) => setForm((p) => ({ ...p, project_id: v, inventory_item_id: "" }))}>
                    <SelectTrigger><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                    <SelectContent>{filteredProjects.map((p) => <SelectItem key={p.id} value={p.id}>{p.code} - {p.name}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-1"><Label>Nombre</Label><Input value={form.nombre} onChange={(e) => setForm((p) => ({ ...p, nombre: e.target.value }))} /></div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1"><Label>Teléfono</Label><Input value={form.telefono} onChange={(e) => setForm((p) => ({ ...p, telefono: e.target.value }))} /></div>
                <div className="space-y-1"><Label>Domicilio</Label><Input value={form.domicilio} onChange={(e) => setForm((p) => ({ ...p, domicilio: e.target.value }))} /></div>
              </div>
              <div className="space-y-1"><Label>Inventario</Label>
                <Select value={form.inventory_item_id || "none"} onValueChange={(v) => setForm((p) => ({ ...p, inventory_item_id: v === "none" ? "" : v }))}>
                  <SelectTrigger><SelectValue placeholder="Sin asignar" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Sin asignar</SelectItem>
                    {companyInventory.map((it) => <SelectItem key={it.id} value={it.id}>{it.lote_edificio}-{it.manzana_departamento}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
                <Button type="submit">Guardar</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader><CardTitle>Listado de clientes</CardTitle></CardHeader>
        <CardContent>
          {loading ? <p className="text-muted-foreground">Cargando...</p> : clients.length === 0 ? <p className="text-muted-foreground">No hay clientes registrados</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-border text-left"><th className="py-2">Nombre</th><th>Empresa</th><th>Proyecto</th><th>Inventario</th><th className="text-right">Acciones</th></tr></thead>
                <tbody>
                  {clients.map((c) => (
                    <tr key={c.id} className="border-b border-border/50">
                      <td className="py-2">{c.nombre}</td>
                      <td>{empresas.find((e) => e.id === c.company_id)?.nombre || "-"}</td>
                      <td>{projects.find((p) => p.id === c.project_id)?.code || "-"}</td>
                      <td>{c.inventory_item_id || "Sin asignar"}</td>
                      <td className="text-right"><Button size="sm" variant="outline" onClick={() => openEdit(c)}>Editar</Button></td>
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
