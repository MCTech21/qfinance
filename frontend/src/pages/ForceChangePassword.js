import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Loader2 } from "lucide-react";

const ForceChangePassword = () => {
  const { forceChangePassword, user } = useAuth();
  const navigate = useNavigate();
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      toast.error("La confirmación no coincide");
      return;
    }

    setIsSaving(true);
    try {
      await forceChangePassword(newPassword);
      toast.success("Contraseña actualizada");
      navigate("/dashboard", { replace: true });
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al cambiar contraseña");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Cambio obligatorio de contraseña</CardTitle>
          <CardDescription>
            {user?.email}: por seguridad debes cambiar tu contraseña antes de continuar.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label>Nueva contraseña</Label>
              <Input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={8} />
            </div>
            <div className="space-y-2">
              <Label>Confirmar nueva contraseña</Label>
              <Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required minLength={8} />
            </div>
            <Button className="w-full" disabled={isSaving} type="submit">
              {isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Cambiar contraseña
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default ForceChangePassword;
