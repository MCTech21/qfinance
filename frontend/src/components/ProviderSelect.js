import { useEffect, useMemo, useState } from "react";
import { Input } from "./ui/input";
import { Button } from "./ui/button";

export default function ProviderSelect({ apiClient, value, onChange, disabled = false, canCreate = false }) {
  const [q, setQ] = useState("");
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await apiClient().get("/providers", { params: { q: q || undefined } });
        setProviders(res.data || []);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [apiClient, q]);

  const selected = useMemo(() => providers.find((p) => p.id === value), [providers, value]);

  const quickCreate = async () => {
    const name = window.prompt("Nombre del proveedor");
    if (!name) return;
    const code = `AUTO-${Date.now()}`;
    const res = await apiClient().post("/providers", { code, name, rfc: "XAXX010101000", is_active: true });
    onChange(res.data?.id || "");
    setQ("");
  };

  return (
    <div className="space-y-2">
      <Input placeholder="Buscar proveedor por nombre/RFC/código" value={q} onChange={(e) => setQ(e.target.value)} disabled={disabled} />
      <select
        className="w-full border rounded-md p-2 bg-background"
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      >
        <option value="">Manual</option>
        {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      {loading && <p className="text-xs text-muted-foreground">Buscando...</p>}
      {!loading && !providers.length && canCreate && <Button type="button" variant="outline" size="sm" onClick={quickCreate}>Crear proveedor rápido</Button>}
      {selected && <p className="text-xs text-muted-foreground">Seleccionado: {selected.name}</p>}
    </div>
  );
}
