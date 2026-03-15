import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "./ui/dialog";
import { Button } from "./ui/button";

export default function ImportClientesCSVModal({ onImportSuccess, trigger }) {
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
      const res = await api().post("/clients/import-csv?dry_run=false", formData, {
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
          <DialogTitle>Importar Clientes desde CSV</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <p className="text-sm font-medium mb-2">Formato requerido del CSV:</p>
            <div className="bg-black text-green-400 p-3 rounded font-mono text-xs break-all">
              company_id,project_id,nombre,telefono,domicilio,code
            </div>
          </div>

          <div className="text-sm space-y-1">
            <p className="font-medium">Especificaciones:</p>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground">
              <li>company_id: ID de la empresa (obligatorio)</li>
              <li>project_id: ID del proyecto (obligatorio)</li>
              <li>nombre: Nombre completo del cliente (obligatorio)</li>
              <li>telefono: Teléfono de contacto (opcional)</li>
              <li>domicilio: Dirección/domicilio (opcional)</li>
              <li>code: Código único del cliente (opcional, si no se provee el sistema lo genera automáticamente)</li>
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
            <p>Nota: El código del cliente es opcional. Si no se provee, el backend lo genera automáticamente.</p>
            <p className="mt-1">Nota: La propiedad asignada del cliente se define después en la pantalla de edición (no en el CSV).</p>
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button onClick={handleImport}>Importar Clientes</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
