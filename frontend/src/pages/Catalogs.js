import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import ImportProveedoresCSVModal from "../components/ImportProveedoresCSVModal";
import { Plus, Pencil, Truck, Loader2, Upload, Download } from "lucide-react";

const Catalogs = () => {
  const { api } = useAuth();
  const [providers, setProviders] = useState([]);
  const [showInactive, setShowInactive] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState({ code: "", name: "", rfc: "" });

  const fetchProviders = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await api().get("/providers", { params: { include_inactive: showInactive } });
      setProviders(res.data);
    } catch {
      toast.error("Error al cargar proveedores");
    } finally {
      setIsLoading(false);
    }
  }, [api, showInactive]);

  useEffect(() => { fetchProviders(); }, [fetchProviders]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      if (editingItem) await api().put(`/providers/${editingItem.id}`, { ...editingItem, ...formData });
      else await api().post("/providers", { ...formData, is_active: true });
      toast.success("Proveedor guardado");
      setDialogOpen(false);
      setEditingItem(null);
      setFormData({ code: "", name: "", rfc: "" });
      fetchProviders();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al guardar proveedor");
    } finally { setIsSaving(false); }
  };

  const toggleActive = async (item) => {
    try {
      await api().put(`/providers/${item.id}/toggle`);
      toast.success("Proveedor actualizado");
      fetchProviders();
    } catch { toast.error("Error al actualizar estado"); }
  };

  const exportProviders = async (format) => {
    const res = await api().get(`/providers/export?format=${format}`, { responseType: "blob" });
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const a = document.createElement("a");
    a.href = url;
    a.download = `providers.${format}`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6" data-testid="catalogs-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight">Proveedores</h1>
          <p className="text-muted-foreground">Catálogo de proveedores (activar/desactivar)</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => exportProviders("csv")}><Download className="h-4 w-4 mr-2" />Export CSV</Button>
          <Button variant="outline" onClick={() => exportProviders("xlsx")}><Download className="h-4 w-4 mr-2" />Export XLSX</Button>
          <ImportProveedoresCSVModal
            onImportSuccess={() => fetchProviders()}
            trigger={<Button variant="outline"><Upload className="h-4 w-4 mr-2" />Importar</Button>}
          />
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild><Button><Plus className="h-4 w-4 mr-2" />Nuevo Proveedor</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>{editingItem ? "Editar" : "Nuevo"} Proveedor</DialogTitle></DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2"><Label>Código</Label><Input placeholder="code (opcional - se genera automáticamente)" value={formData.code || ""} onChange={(e) => setFormData((p) => ({ ...p, code: e.target.value.toUpperCase() }))} /></div>
                <div className="space-y-2"><Label>Nombre</Label><Input value={formData.name} onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))} required /></div>
                <div className="space-y-2"><Label>RFC</Label><Input value={formData.rfc} onChange={(e) => setFormData((p) => ({ ...p, rfc: e.target.value.toUpperCase() }))} /></div>
                <DialogFooter><Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button><Button type="submit" disabled={isSaving}>{isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}Guardar</Button></DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Card>
        <CardHeader><CardTitle className="font-heading text-lg"><Truck className="h-4 w-4 inline mr-2" />Lista de Proveedores</CardTitle></CardHeader>
        <CardContent>
          <label className="text-sm flex items-center gap-2 mb-4"><input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />ver inactivos</label>
          {isLoading ? <div className="flex justify-center py-8"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div> : (
            <table className="data-table" data-testid="providers-table"><thead><tr><th>Código</th><th>Nombre</th><th>RFC</th><th>Estatus</th><th>Acciones</th></tr></thead><tbody>
              {providers.map((item) => (<tr key={item.id}><td>{item.code}</td><td>{item.name}</td><td>{item.rfc || "-"}</td><td>{item.is_active === false ? "Inactivo" : "Activo"}</td><td className="space-x-1"><Button variant="ghost" size="icon" onClick={() => { setEditingItem(item); setFormData({ code: item.code, name: item.name, rfc: item.rfc || "" }); setDialogOpen(true); }}><Pencil className="h-4 w-4" /></Button><Button variant="outline" size="sm" onClick={() => toggleActive(item)}>{item.is_active === false ? "Activar" : "Desactivar"}</Button></td></tr>))}
            </tbody></table>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default Catalogs;
