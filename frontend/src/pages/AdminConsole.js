import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";

const entityConfig = {
  empresas: { label: "Empresas", fields: ["nombre"] },
  proyectos: { label: "Proyectos", fields: ["code", "name", "empresa_id", "description"] },
  catalogo_partidas: { label: "Partidas", fields: ["codigo", "nombre", "grupo"] },
  proveedores: { label: "Proveedores", fields: ["code", "name", "rfc"] },
  usuarios: { label: "Usuarios", fields: ["email", "name", "role", "is_active"] },
};

const AdminConsole = () => {
  const { api } = useAuth();
  const [tab, setTab] = useState("empresas");
  const [rows, setRows] = useState([]);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [search, setSearch] = useState("");
  const [form, setForm] = useState({});
  const [editingId, setEditingId] = useState(null);
  const [postedMovements, setPostedMovements] = useState([]);
  const [empresasCatalog, setEmpresasCatalog] = useState([]);

  const loadRows = useCallback(async () => {
    const response = await api().get(`/admin/catalogs/${tab}`, { params: { include_inactive: includeInactive } });
    setRows(response.data || []);
  }, [api, tab, includeInactive]);

  useEffect(() => {
    loadRows().catch(() => toast.error("No se pudo cargar admin"));
  }, [loadRows]);

  useEffect(() => {
    if (tab === "proyectos") {
      api().get("/admin/catalogs/empresas", { params: { include_inactive: true } }).then((r) => setEmpresasCatalog(r.data || [])).catch(() => setEmpresasCatalog([]));
    }
  }, [api, tab]);

  const filtered = useMemo(() => {
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter((row) => JSON.stringify(row).toLowerCase().includes(q));
  }, [rows, search]);

  const submit = async (e) => {
    e.preventDefault();
    try {
      if (editingId) {
        await api().put(`/admin/catalogs/${tab}/${editingId}`, form);
        toast.success("Actualizado");
      } else {
        await api().post(`/admin/catalogs/${tab}`, form);
        toast.success("Creado");
      }
      setForm({});
      setEditingId(null);
      await loadRows();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Error al guardar");
    }
  };

  const softDelete = async (row) => {
    try {
      await api().delete(`/admin/catalogs/${tab}/${row.id}`);
      toast.success("Desactivado");
      await loadRows();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Error al desactivar");
    }
  };

  const restore = async (row) => {
    await api().post(`/admin/catalogs/${tab}/${row.id}/restore`);
    toast.success("Restaurado");
    await loadRows();
  };

  const hardDelete = async (row) => {
    try {
      await api().delete(`/admin/catalogs/${tab}/${row.id}`, { params: { hard_delete: true } });
      toast.success("Eliminado físicamente");
      await loadRows();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Bloqueado por referencias");
    }
  };

  const reverseMovement = async (id) => {
    try {
      await api().post(`/admin/movimientos/${id}/reverse`);
      toast.success("Reversa creada");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Error al revertir");
    }
  };

  const columns = entityConfig[tab].fields;

  return (
    <div className="space-y-6" data-testid="admin-console-page">
      <div className="flex flex-wrap items-center gap-2">
        {Object.entries(entityConfig).map(([key, item]) => (
          <Button key={key} variant={tab === key ? "default" : "outline"} onClick={() => { setTab(key); setForm({}); setEditingId(null); }}>
            {item.label}
          </Button>
        ))}
      </div>

      <div className="space-y-3 border border-border rounded-lg p-4">
        <h3 className="font-semibold">{editingId ? "Editar" : "Crear"} {entityConfig[tab].label}</h3>
        <form onSubmit={submit} className="space-y-2">
          {columns.map((field) => (
            tab === "proyectos" && field === "empresa_id" ? (
              <select
                key={field}
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={form[field] ?? ""}
                onChange={(e) => setForm((prev) => ({ ...prev, [field]: e.target.value }))}
                required
              >
                <option value="">Selecciona empresa...</option>
                {empresasCatalog.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
              </select>
            ) : (
              <Input
                key={field}
                placeholder={field}
                value={form[field] ?? ""}
                onChange={(e) => setForm((prev) => ({ ...prev, [field]: e.target.value }))}
              />
            )
          ))}
          {tab === "usuarios" && !editingId && (
            <Input placeholder="password" type="password" value={form.password ?? ""} onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))} />
          )}
          <div className="flex gap-2">
            <Button type="submit">Guardar</Button>
            {editingId && <Button type="button" variant="outline" onClick={() => { setEditingId(null); setForm({}); }}>Cancelar</Button>}
          </div>
        </form>
      </div>

      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Input placeholder="Buscar..." value={search} onChange={(e) => setSearch(e.target.value)} />
          <label className="text-sm flex items-center gap-1">
            <input type="checkbox" checked={includeInactive} onChange={(e) => setIncludeInactive(e.target.checked)} /> ver inactivos
          </label>
        </div>

        <div className="overflow-auto border border-border rounded-lg">
          <table className="data-table w-full text-sm">
            <thead>
              <tr>
                <th>ID</th>
                {columns.map((c) => <th key={c}>{c}</th>)}
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr key={row.id}>
                  <td className="max-w-[120px] truncate">{row.id}</td>
                  {columns.map((c) => <td key={c}>{String(row[c] ?? "")}</td>)}
                  <td className="space-x-1 whitespace-nowrap">
                    <Button size="sm" variant="outline" onClick={() => { setEditingId(row.id); setForm(Object.fromEntries(columns.map((c) => [c, row[c] ?? ""]))); }}>Editar</Button>
                    {row.is_active === false
                      ? <Button size="sm" onClick={() => restore(row)}>Restaurar</Button>
                      : <Button size="sm" variant="secondary" onClick={() => softDelete(row)}>Desactivar</Button>
                    }
                    <Button size="sm" variant="destructive" onClick={() => hardDelete(row)}>Hard delete</Button>
                    {tab === "usuarios" && (
                      <Button size="sm" variant="outline" onClick={() => api().put(`/admin/catalogs/usuarios/${row.id}`, { role: row.role === "admin" ? "finanzas" : "admin" }).then(loadRows)}>
                        Toggle admin
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="space-y-2 border border-border rounded-lg p-4">
        <h3 className="font-semibold">Movimientos posted (reversal)</h3>
        <Button variant="outline" onClick={async () => {
          const res = await api().get("/admin/movimientos");
          const posted = (res.data || []).filter((m) => m.status === "posted").slice(0, 10);
          setPostedMovements(posted);
        }}>Cargar movimientos posted (últimos 10)</Button>
        <div className="text-xs text-muted-foreground">Para reversar un movimiento usa este botón desde API o integra en lista de movimientos.</div>
        <div className="flex flex-wrap gap-2">
          {(postedMovements || []).map((m) => (
            <Button key={m.id} size="sm" onClick={() => reverseMovement(m.id)}>Reverse {m.reference || m.id.slice(0, 6)}</Button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default AdminConsole;
