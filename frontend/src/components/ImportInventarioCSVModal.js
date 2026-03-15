import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "./ui/dialog";
import { Button } from "./ui/button";

export default function ImportInventarioCSVModal({ onImportSuccess, trigger }) {
  const { api } = useAuth();
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState(null);

  const handleOpenChange = (isOpen) => {
    setOpen(isOpen);
    if (!isOpen) {
      setFile(null);
    }
  };

  const handleImport = async () => {
    if (!file) return toast.error("Selecciona un archivo CSV");
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await api().post("/inventory/import-csv?dry_run=false", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      toast.success(`Importación completada: ${res.data.created_count} creados, ${res.data.updated_count} actualizados, ${res.data.skipped_count} omitidos`);
      if (res.data.errors?.length) toast.error(`Errores: ${res.data.errors.length}`);

      setOpen(false);
      setFile(null);
      if (onImportSuccess) onImportSuccess();
    } catch (error) {
      toast.error(error?.response?.data?.detail?.message || "Error en importación CSV");
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Importar Inventario desde CSV</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <p className="text-sm font-medium mb-2">Formato requerido del CSV:</p>
            <div className="bg-black text-green-400 p-3 rounded font-mono text-xs break-all">
              company_id,project_id,m2_superficie,m2_construccion,lote_edificio,manzana_departamento,precio_m2_superficie,precio_m2_construccion,descuento_bonificacion,code
            </div>
          </div>

          <div className="text-sm space-y-1">
            <p className="font-medium">Especificaciones:</p>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground">
              <li>company_id: ID de la empresa (obligatorio)</li>
              <li>project_id: ID del proyecto (obligatorio)</li>
              <li>m2_superficie: Metros cuadrados de superficie (obligatorio, número decimal)</li>
              <li>m2_construccion: Metros cuadrados de construcción (número decimal, default: 0)</li>
              <li>lote_edificio: Identificador de lote o edificio (obligatorio)</li>
              <li>manzana_departamento: Identificador de manzana o departamento (obligatorio)</li>
              <li>precio_m2_superficie: Precio por m2 de superficie (obligatorio, número decimal)</li>
              <li>precio_m2_construccion: Precio por m2 de construcción (número decimal, default: 0)</li>
              <li>descuento_bonificacion: Descuento o bonificación aplicada (número decimal, default: 0)</li>
              <li>code: Código único SKU (opcional, si no se provee el sistema busca duplicados por company+project+lote+manzana)</li>
            </ul>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Seleccionar archivo</label>
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-primary file:text-primary-foreground hover:file:bg-primary/90"
            />
          </div>

          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            <p>Nota: Los campos calculados precio_venta y precio_total no se importan desde CSV; el backend los calcula automáticamente.</p>
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button onClick={handleImport}>Importar Inventario</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
