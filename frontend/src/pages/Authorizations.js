import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { CheckCircle, XCircle, Clock, Loader2, AlertTriangle } from "lucide-react";

const Authorizations = () => {
  const { api } = useAuth();
  const [authorizations, setAuthorizations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [resolving, setResolving] = useState(null);
  const [notes, setNotes] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedAuth, setSelectedAuth] = useState(null);
  const [action, setAction] = useState(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await api().get("/authorizations");
      setAuthorizations(response.data);
    } catch (error) {
      toast.error("Error al cargar autorizaciones");
    } finally {
      setIsLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleResolve = async () => {
    if (!selectedAuth || !action) return;
    
    setResolving(selectedAuth.id);
    try {
      await api().put(`/authorizations/${selectedAuth.id}`, {
        status: action,
        notes: notes
      });
      
      toast.success(action === "approved" ? "Autorización aprobada" : "Autorización rechazada");
      setDialogOpen(false);
      setSelectedAuth(null);
      setNotes("");
      fetchData();
    } catch (error) {
      toast.error("Error al procesar autorización");
    } finally {
      setResolving(null);
    }
  };

  const openResolveDialog = (auth, actionType) => {
    setSelectedAuth(auth);
    setAction(actionType);
    setNotes("");
    setDialogOpen(true);
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleString("es-MX", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  const pendingAuths = authorizations.filter(a => a.status === "pending");
  const resolvedAuths = authorizations.filter(a => a.status !== "pending");

  const statusConfig = {
    pending: { icon: Clock, color: "text-amber-400", bg: "bg-amber-500/10", label: "Pendiente" },
    approved: { icon: CheckCircle, color: "text-emerald-400", bg: "bg-emerald-500/10", label: "Aprobado" },
    rejected: { icon: XCircle, color: "text-red-400", bg: "bg-red-500/10", label: "Rechazado" }
  };

  return (
    <div className="space-y-6" data-testid="authorizations-page">
      <div>
        <h1 className="font-heading text-3xl font-bold tracking-tight">Autorizaciones</h1>
        <p className="text-muted-foreground">Gestión de autorizaciones para excesos de presupuesto</p>
      </div>

      {/* Pending */}
      <Card>
        <CardHeader>
          <CardTitle className="font-heading text-lg flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-400" />
            Pendientes de Autorización ({pendingAuths.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : pendingAuths.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No hay autorizaciones pendientes
            </div>
          ) : (
            <div className="space-y-4">
              {pendingAuths.map(auth => (
                <div
                  key={auth.id}
                  className="p-4 border border-border rounded-lg bg-card hover:border-amber-500/30 transition-colors"
                  data-testid={`auth-item-${auth.id}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge variant="outline" className="text-amber-400 border-amber-500/30">
                          <Clock className="h-3 w-3 mr-1" />
                          Pendiente
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {formatDate(auth.created_at)}
                        </span>
                      </div>
                      <p className="font-medium mb-1">{auth.reason}</p>
                      <p className="text-sm text-muted-foreground">
                        ID Movimiento: {auth.movement_id || "N/A"}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/10"
                        onClick={() => openResolveDialog(auth, "approved")}
                        disabled={resolving === auth.id}
                        data-testid={`approve-auth-${auth.id}`}
                      >
                        <CheckCircle className="h-4 w-4 mr-1" />
                        Aprobar
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-red-400 border-red-500/30 hover:bg-red-500/10"
                        onClick={() => openResolveDialog(auth, "rejected")}
                        disabled={resolving === auth.id}
                        data-testid={`reject-auth-${auth.id}`}
                      >
                        <XCircle className="h-4 w-4 mr-1" />
                        Rechazar
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Resolved */}
      <Card>
        <CardHeader>
          <CardTitle className="font-heading text-lg">Historial de Autorizaciones</CardTitle>
        </CardHeader>
        <CardContent>
          {resolvedAuths.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No hay historial de autorizaciones
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table" data-testid="auth-history-table">
                <thead>
                  <tr>
                    <th>Fecha Solicitud</th>
                    <th>Razón</th>
                    <th>Estado</th>
                    <th>Fecha Resolución</th>
                    <th>Notas</th>
                  </tr>
                </thead>
                <tbody>
                  {resolvedAuths.map(auth => {
                    const config = statusConfig[auth.status];
                    const Icon = config?.icon || Clock;
                    return (
                      <tr key={auth.id}>
                        <td className="font-mono text-sm">{formatDate(auth.created_at)}</td>
                        <td className="max-w-[300px]">{auth.reason}</td>
                        <td>
                          <Badge variant="outline" className={`${config?.color} ${config?.bg}`}>
                            <Icon className="h-3 w-3 mr-1" />
                            {config?.label}
                          </Badge>
                        </td>
                        <td className="font-mono text-sm">
                          {auth.resolved_at ? formatDate(auth.resolved_at) : "-"}
                        </td>
                        <td className="text-muted-foreground text-sm">{auth.notes || "-"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Resolve Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {action === "approved" ? "Aprobar Autorización" : "Rechazar Autorización"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-4 bg-muted rounded-lg">
              <p className="font-medium">{selectedAuth?.reason}</p>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Notas (opcional)</label>
              <Textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Agregar comentarios sobre la decisión..."
                rows={3}
                data-testid="auth-notes-input"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={handleResolve}
              disabled={resolving}
              className={action === "approved" 
                ? "bg-emerald-600 hover:bg-emerald-700" 
                : "bg-red-600 hover:bg-red-700"
              }
              data-testid="confirm-auth-btn"
            >
              {resolving && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              {action === "approved" ? "Confirmar Aprobación" : "Confirmar Rechazo"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Authorizations;
