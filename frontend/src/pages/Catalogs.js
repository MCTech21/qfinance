import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import { Plus, Pencil, Building, FolderTree, Truck, Loader2 } from "lucide-react";

const Catalogs = () => {
  const { api } = useAuth();
  const [activeTab, setActiveTab] = useState("projects");
  const [projects, setProjects] = useState([]);
  const [partidas, setPartidas] = useState([]);
  const [providers, setProviders] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  
  const [formData, setFormData] = useState({
    code: "",
    name: "",
    description: "",
    rfc: ""
  });

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [projectsRes, partidasRes, providersRes] = await Promise.all([
        api().get("/projects"),
        api().get("/partidas"),
        api().get("/providers")
      ]);
      setProjects(projectsRes.data);
      setPartidas(partidasRes.data);
      setProviders(providersRes.data);
    } catch (error) {
      toast.error("Error al cargar catálogos");
    } finally {
      setIsLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleOpenDialog = (item = null) => {
    if (item) {
      setEditingItem(item);
      setFormData({
        code: item.code,
        name: item.name,
        description: item.description || "",
        rfc: item.rfc || ""
      });
    } else {
      setEditingItem(null);
      setFormData({ code: "", name: "", description: "", rfc: "" });
    }
    setDialogOpen(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    
    const endpoint = activeTab === "projects" ? "projects" : activeTab === "partidas" ? "partidas" : "providers";
    
    try {
      if (editingItem) {
        await api().put(`/${endpoint}/${editingItem.id}`, formData);
        toast.success("Registro actualizado");
      } else {
        await api().post(`/${endpoint}`, formData);
        toast.success("Registro creado");
      }
      
      setDialogOpen(false);
      fetchData();
    } catch (error) {
      const message = error.response?.data?.detail || "Error al guardar";
      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  };

  const getTabData = () => {
    switch (activeTab) {
      case "projects": return projects;
      case "partidas": return partidas;
      case "providers": return providers;
      default: return [];
    }
  };

  const getTabTitle = () => {
    switch (activeTab) {
      case "projects": return "Proyectos";
      case "partidas": return "Partidas";
      case "providers": return "Proveedores";
      default: return "";
    }
  };

  return (
    <div className="space-y-6" data-testid="catalogs-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-bold tracking-tight">Catálogos</h1>
          <p className="text-muted-foreground">Gestión de proyectos, partidas y proveedores</p>
        </div>
        
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={() => handleOpenDialog()} data-testid="add-catalog-btn">
              <Plus className="h-4 w-4 mr-2" />
              Nuevo {getTabTitle().slice(0, -1)}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingItem ? `Editar ${getTabTitle().slice(0, -1)}` : `Nuevo ${getTabTitle().slice(0, -1)}`}
              </DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label>Código</Label>
                <Input
                  value={formData.code}
                  onChange={(e) => setFormData(prev => ({ ...prev, code: e.target.value.toUpperCase() }))}
                  placeholder="ABC-001"
                  required
                  data-testid="catalog-code-input"
                />
              </div>
              
              <div className="space-y-2">
                <Label>Nombre</Label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="Nombre del registro"
                  required
                  data-testid="catalog-name-input"
                />
              </div>
              
              <div className="space-y-2">
                <Label>Descripción</Label>
                <Input
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Descripción opcional"
                />
              </div>
              
              {activeTab === "providers" && (
                <div className="space-y-2">
                  <Label>RFC</Label>
                  <Input
                    value={formData.rfc}
                    onChange={(e) => setFormData(prev => ({ ...prev, rfc: e.target.value.toUpperCase() }))}
                    placeholder="ABC123456DEF"
                  />
                </div>
              )}
              
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={isSaving} data-testid="catalog-submit-btn">
                  {isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  {editingItem ? "Actualizar" : "Crear"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3 max-w-md">
          <TabsTrigger value="projects" data-testid="tab-projects">
            <Building className="h-4 w-4 mr-2" />
            Proyectos
          </TabsTrigger>
          <TabsTrigger value="partidas" data-testid="tab-partidas">
            <FolderTree className="h-4 w-4 mr-2" />
            Partidas
          </TabsTrigger>
          <TabsTrigger value="providers" data-testid="tab-providers">
            <Truck className="h-4 w-4 mr-2" />
            Proveedores
          </TabsTrigger>
        </TabsList>

        {["projects", "partidas", "providers"].map(tab => (
          <TabsContent key={tab} value={tab}>
            <Card>
              <CardHeader>
                <CardTitle className="font-heading text-lg">
                  Lista de {tab === "projects" ? "Proyectos" : tab === "partidas" ? "Partidas" : "Proveedores"}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="flex justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                  </div>
                ) : getTabData().length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No hay registros
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="data-table" data-testid={`${tab}-table`}>
                      <thead>
                        <tr>
                          <th>Código</th>
                          <th>Nombre</th>
                          <th>Descripción</th>
                          {tab === "providers" && <th>RFC</th>}
                          <th className="text-right">Acciones</th>
                        </tr>
                      </thead>
                      <tbody>
                        {getTabData().map(item => (
                          <tr key={item.id}>
                            <td className="font-mono text-sm">{item.code}</td>
                            <td>{item.name}</td>
                            <td className="text-muted-foreground text-sm max-w-[200px] truncate">
                              {item.description || "-"}
                            </td>
                            {tab === "providers" && (
                              <td className="font-mono text-sm">{item.rfc || "-"}</td>
                            )}
                            <td className="text-right">
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleOpenDialog(item)}
                                data-testid={`edit-${item.id}`}
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
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
};

export default Catalogs;
