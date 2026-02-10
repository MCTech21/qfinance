import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { ScrollText, Loader2, Filter } from "lucide-react";

const AuditLog = () => {
  const { api } = useAuth();
  const [logs, setLogs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [entityFilter, setEntityFilter] = useState("all");

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = {};
      if (entityFilter !== "all") params.entity = entityFilter;
      
      const response = await api().get("/audit-logs", { params });
      setLogs(response.data);
    } catch (error) {
      toast.error("Error al cargar bitácora");
    } finally {
      setIsLoading(false);
    }
  }, [api, entityFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleString("es-MX", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  const actionColors = {
    CREATE: "bg-emerald-500/15 text-emerald-400",
    UPDATE: "bg-blue-500/15 text-blue-400",
    DELETE: "bg-red-500/15 text-red-400",
    IMPORT: "bg-purple-500/15 text-purple-400",
    RESOLVE: "bg-amber-500/15 text-amber-400"
  };

  const entities = ["all", "users", "projects", "partidas", "providers", "budgets", "movements", "authorizations", "config"];

  return (
    <div className="space-y-6" data-testid="audit-log-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight">Bitácora</h1>
          <p className="text-muted-foreground">Registro de todas las acciones en el sistema</p>
        </div>
        
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <Select value={entityFilter} onValueChange={setEntityFilter}>
            <SelectTrigger className="w-[180px]" data-testid="entity-filter">
              <SelectValue placeholder="Filtrar por entidad" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas las entidades</SelectItem>
              <SelectItem value="users">Usuarios</SelectItem>
              <SelectItem value="projects">Proyectos</SelectItem>
              <SelectItem value="partidas">Partidas</SelectItem>
              <SelectItem value="providers">Proveedores</SelectItem>
              <SelectItem value="budgets">Presupuestos</SelectItem>
              <SelectItem value="movements">Movimientos</SelectItem>
              <SelectItem value="authorizations">Autorizaciones</SelectItem>
              <SelectItem value="config">Configuración</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="font-heading text-lg flex items-center gap-2">
            <ScrollText className="h-5 w-5" />
            Registros de Auditoría ({logs.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No hay registros de auditoría
            </div>
          ) : (
            <div className="space-y-3">
              {logs.map((log, idx) => (
                <div
                  key={log.id || idx}
                  className="p-4 border border-border rounded-lg hover:border-primary/30 transition-colors"
                  data-testid={`audit-log-${idx}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge className={actionColors[log.action] || "bg-muted"}>
                          {log.action}
                        </Badge>
                        <Badge variant="outline">{log.entity}</Badge>
                        <span className="text-xs text-muted-foreground font-mono">
                          {log.entity_id}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <span className="font-medium">{log.user_email}</span>
                        <span className="text-muted-foreground">({log.user_role})</span>
                      </div>
                    </div>
                    <span className="text-xs text-muted-foreground font-mono whitespace-nowrap">
                      {formatDate(log.timestamp)}
                    </span>
                  </div>
                  
                  {log.changes && Object.keys(log.changes).length > 0 && (
                    <div className="mt-3 p-3 bg-muted/50 rounded text-xs font-mono overflow-x-auto">
                      <pre className="whitespace-pre-wrap">
                        {JSON.stringify(log.changes, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default AuditLog;
