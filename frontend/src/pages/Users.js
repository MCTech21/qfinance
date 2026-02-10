import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Label } from "../components/ui/label";
import { Users as UsersIcon, Pencil, Loader2, Shield } from "lucide-react";

const roleOptions = [
  { value: "admin", label: "Administrador" },
  { value: "finanzas", label: "Finanzas" },
  { value: "autorizador", label: "Autorizador" },
  { value: "solo_lectura", label: "Solo Lectura" }
];

const roleBadgeColors = {
  admin: "bg-red-500/15 text-red-400 border-red-500/30",
  finanzas: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  autorizador: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  solo_lectura: "bg-slate-500/15 text-slate-400 border-slate-500/30"
};

const Users = () => {
  const { api, user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [selectedRole, setSelectedRole] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await api().get("/users");
      setUsers(response.data);
    } catch (error) {
      toast.error("Error al cargar usuarios");
    } finally {
      setIsLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleEditRole = (user) => {
    setEditingUser(user);
    setSelectedRole(user.role);
    setDialogOpen(true);
  };

  const handleSaveRole = async () => {
    if (!editingUser) return;
    
    setIsSaving(true);
    try {
      await api().put(`/users/${editingUser.id}`, { role: selectedRole });
      toast.success("Rol actualizado");
      setDialogOpen(false);
      fetchData();
    } catch (error) {
      toast.error("Error al actualizar rol");
    } finally {
      setIsSaving(false);
    }
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString("es-MX", {
      day: "2-digit",
      month: "short",
      year: "numeric"
    });
  };

  return (
    <div className="space-y-6" data-testid="users-page">
      <div>
        <h1 className="font-heading text-3xl font-bold tracking-tight">Usuarios</h1>
        <p className="text-muted-foreground">Gestión de usuarios y roles del sistema</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="font-heading text-lg flex items-center gap-2">
            <UsersIcon className="h-5 w-5" />
            Lista de Usuarios ({users.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : users.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No hay usuarios registrados
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table" data-testid="users-table">
                <thead>
                  <tr>
                    <th>Nombre</th>
                    <th>Email</th>
                    <th>Rol</th>
                    <th>Estado</th>
                    <th>Creado</th>
                    <th className="text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(user => (
                    <tr key={user.id}>
                      <td className="font-medium">{user.name}</td>
                      <td className="text-muted-foreground">{user.email}</td>
                      <td>
                        <Badge variant="outline" className={roleBadgeColors[user.role]}>
                          <Shield className="h-3 w-3 mr-1" />
                          {roleOptions.find(r => r.value === user.role)?.label || user.role}
                        </Badge>
                      </td>
                      <td>
                        <Badge variant={user.is_active ? "default" : "secondary"}>
                          {user.is_active ? "Activo" : "Inactivo"}
                        </Badge>
                      </td>
                      <td className="font-mono text-sm">{formatDate(user.created_at)}</td>
                      <td className="text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleEditRole(user)}
                          disabled={user.id === currentUser?.id}
                          data-testid={`edit-user-${user.id}`}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Role Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Editar Rol de Usuario</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-4 bg-muted rounded-lg">
              <p className="font-medium">{editingUser?.name}</p>
              <p className="text-sm text-muted-foreground">{editingUser?.email}</p>
            </div>
            
            <div className="space-y-2">
              <Label>Rol</Label>
              <Select value={selectedRole} onValueChange={setSelectedRole}>
                <SelectTrigger data-testid="role-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {roleOptions.map(role => (
                    <SelectItem key={role.value} value={role.value}>
                      {role.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div className="p-4 bg-muted/50 rounded-lg text-sm">
              <p className="font-medium mb-2">Permisos del rol:</p>
              <ul className="text-muted-foreground space-y-1">
                {selectedRole === "admin" && (
                  <>
                    <li>• Gestión completa del sistema</li>
                    <li>• Administración de usuarios y roles</li>
                    <li>• Configuración de catálogos</li>
                    <li>• Ver bitácora de auditoría</li>
                  </>
                )}
                {selectedRole === "finanzas" && (
                  <>
                    <li>• Crear y editar presupuestos</li>
                    <li>• Registrar e importar movimientos</li>
                    <li>• Ver reportes y exportar</li>
                  </>
                )}
                {selectedRole === "autorizador" && (
                  <>
                    <li>• Aprobar/rechazar excesos de presupuesto</li>
                    <li>• Ver dashboard y reportes</li>
                    <li>• Ver bitácora de auditoría</li>
                  </>
                )}
                {selectedRole === "solo_lectura" && (
                  <>
                    <li>• Ver dashboard</li>
                    <li>• Ver reportes y exportar</li>
                  </>
                )}
              </ul>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={handleSaveRole} disabled={isSaving} data-testid="save-role-btn">
              {isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Guardar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Users;
