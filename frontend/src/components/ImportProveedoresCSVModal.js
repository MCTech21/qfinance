import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "./ui/dialog";
import { Button } from "./ui/button";

export default function ImportProveedoresCSVModal({ onImportSuccess, trigger }) {
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
    if (!file) return toast.error("Selecciona un archivo CSV o XLSX");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await api().post("/providers/import", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      toast.success(`Importación completada: ${res.data.created} creados, ${res.data.updated} actualizados`);

      if (res.data.duplicates?.length > 0) {
        toast.warning(`${res.data.duplicates.length} filas duplicadas omitidas`);
      }

      if (res.data.errors?.length > 0) {
        toast.error(`${res.data.errors.length} errores en importación`);
      }

      setOpen(false);
      setFile(null);
      if (onImportSuccess) onImportSuccess();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Error en importación");
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Importar Proveedores desde CSV/XLSX</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <p className="text-sm font-medium mb-2">Formato requerido del CSV:</p>
            <div className="bg-black text-green-400 p-3 rounded font-mono text-xs">code,name,rfc,is_active</div>
          </div>

          <div className="text-sm space-y-1">
            <p className="font-medium">Especificaciones:</p>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground">
              <li><strong>code</strong>: Código único del proveedor (obligatorio, se convierte a mayúsculas automáticamente)</li>
              <li><strong>name</strong>: Nombre o razón social del proveedor (obligatorio)</li>
              <li><strong>rfc</strong>: RFC del proveedor (opcional, se convierte a mayúsculas)</li>
              <li><strong>is_active</strong>: Estado activo/inactivo (opcional, valores: true/false/1/0/yes/no/active/inactive, default: true)</li>
            </ul>
          </div>

          <div className="bg-blue-50 dark:bg-blue-950 p-3 rounded text-sm">
            <p className="font-medium mb-1">IMPORTANTE:</p>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground">
              <li>El archivo puede ser CSV o XLSX</li>
              <li>Si se detecta un código duplicado dentro del mismo archivo, la fila se omite</li>
              <li>Si un proveedor ya existe (mismo code), se actualiza con los nuevos datos</li>
              <li>Los códigos se normalizan a MAYÚSCULAS automáticamente</li>
            </ul>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Seleccionar archivo</label>
            <input
              type="file"
              accept=".csv,.xlsx"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-primary file:text-primary-foreground hover:file:bg-primary/90"
            />
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button onClick={handleImport}>Importar Proveedores</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
