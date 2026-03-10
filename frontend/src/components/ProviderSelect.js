import { useEffect, useMemo, useRef, useState } from "react";
import { Input } from "./ui/input";
import { Button } from "./ui/button";

const normalizeSearchText = (value) => String(value || "")
  .normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "")
  .toLowerCase()
  .trim();

const tokenize = (value) => normalizeSearchText(value).split(/\s+/).filter(Boolean);

const rankProviders = (rows, query) => {
  const q = normalizeSearchText(query);
  const sorted = [...(rows || [])];
  if (!q) {
    return sorted.sort((a, b) => normalizeSearchText(a?.name).localeCompare(normalizeSearchText(b?.name)));
  }
  const scoreOf = (provider) => {
    const name = normalizeSearchText(provider?.name);
    const code = normalizeSearchText(provider?.code);
    const rfc = normalizeSearchText(provider?.rfc);
    const fields = [name, code, rfc].filter(Boolean);
    if (fields.some((f) => f === q)) return 0;
    if (fields.some((f) => f.startsWith(q))) return 1;
    if (fields.some((f) => tokenize(f).some((token) => token.startsWith(q)))) return 2;
    if (fields.some((f) => f.includes(q))) return 3;
    return 4;
  };
  return sorted.sort((a, b) => {
    const scoreDiff = scoreOf(a) - scoreOf(b);
    if (scoreDiff !== 0) return scoreDiff;
    return normalizeSearchText(a?.name).localeCompare(normalizeSearchText(b?.name));
  });
};

const renderHighlight = (text, query) => {
  const value = String(text || "");
  const q = String(query || "").trim();
  if (!q) return value;
  const lower = value.toLowerCase();
  const qLower = q.toLowerCase();
  const at = lower.indexOf(qLower);
  if (at < 0) return value;
  return (
    <>
      {value.slice(0, at)}
      <mark className="bg-yellow-200/80 rounded-sm px-0.5">{value.slice(at, at + q.length)}</mark>
      {value.slice(at + q.length)}
    </>
  );
};

export default function ProviderSelect({ apiClient, value, onChange, disabled = false, canCreate = false }) {
  const [q, setQ] = useState("");
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [selectedProvider, setSelectedProvider] = useState(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    let ignore = false;
    if (!value) {
      setSelectedProvider(null);
      return;
    }
    (async () => {
      try {
        const res = await apiClient().get("/providers", { params: { limit: 100 } });
        if (ignore) return;
        const found = (res.data || []).find((p) => p.id === value) || null;
        setSelectedProvider(found);
        if (found && !open) setQ(found.name || "");
      } catch {
        if (!ignore) setSelectedProvider(null);
      }
    })();
    return () => { ignore = true; };
  }, [apiClient, value, open]);

  useEffect(() => {
    const requestId = ++requestIdRef.current;
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const trimmed = q.trim();
        const params = trimmed.length >= 1 ? { q: trimmed, limit: 20 } : { q: "", limit: 50 };
        const res = await apiClient().get("/providers", { params });
        if (requestId !== requestIdRef.current) return;
        const rows = rankProviders(res.data || [], trimmed);
        setProviders(rows);
        setActiveIndex(rows.length ? 0 : -1);
      } finally {
        if (requestId === requestIdRef.current) setLoading(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [apiClient, q]);

  const selected = useMemo(() => providers.find((p) => p.id === value) || selectedProvider, [providers, selectedProvider, value]);

  const applySelected = (provider) => {
    if (!provider) return;
    onChange(provider.id, provider);
    setQ(provider.name || "");
    setOpen(false);
    setSelectedProvider(provider);
  };

  const quickCreate = async () => {
    const name = window.prompt("Nombre del proveedor");
    if (!name) return;
    const code = `AUTO-${Date.now()}`;
    const res = await apiClient().post("/providers", { code, name, rfc: "XAXX010101000", is_active: true });
    const created = res.data || null;
    onChange(created?.id || "", created);
    setQ(created?.name || name);
    setOpen(false);
  };

  return (
    <div className="space-y-2 relative">
      <Input
        role="combobox"
        aria-expanded={open}
        aria-controls="provider-combobox-list"
        placeholder="Buscar proveedor por nombre/RFC/código"
        value={q}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onKeyDown={(e) => {
          if (!open && (e.key === "ArrowDown" || e.key === "ArrowUp")) setOpen(true);
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActiveIndex((idx) => Math.min(idx + 1, providers.length - 1));
          }
          if (e.key === "ArrowUp") {
            e.preventDefault();
            setActiveIndex((idx) => Math.max(idx - 1, 0));
          }
          if (e.key === "Enter" && open && activeIndex >= 0) {
            e.preventDefault();
            applySelected(providers[activeIndex]);
          }
          if (e.key === "Escape") setOpen(false);
        }}
        disabled={disabled}
      />
      {open && (
        <div id="provider-combobox-list" className="absolute z-50 mt-1 w-full rounded-md border bg-background shadow max-h-64 overflow-auto">
          {loading && <p className="px-3 py-2 text-xs text-muted-foreground">Buscando...</p>}
          {!loading && providers.map((p, idx) => (
            <button
              key={p.id}
              type="button"
              className={`w-full text-left px-3 py-2 text-sm hover:bg-muted ${idx === activeIndex ? "bg-muted" : ""}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => applySelected(p)}
            >
              {renderHighlight(p.name, q)}
              {p.rfc ? <span className="text-muted-foreground"> — {renderHighlight(p.rfc, q)}</span> : null}
            </button>
          ))}
          {!loading && !providers.length && (
            <div className="px-3 py-2 text-sm text-muted-foreground">
              <p>Sin resultados</p>
              {canCreate && <Button type="button" variant="outline" size="sm" onClick={quickCreate} className="mt-2">Crear proveedor rápido</Button>}
            </div>
          )}
        </div>
      )}
      {selected && <p className="text-xs text-muted-foreground">Seleccionado: {selected.name}</p>}
    </div>
  );
}
