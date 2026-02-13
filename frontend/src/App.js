import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Budgets from "./pages/Budgets";
import Movements from "./pages/Movements";
import Authorizations from "./pages/Authorizations";
import Reports from "./pages/Reports";
import Catalogs from "./pages/Catalogs";
import Users from "./pages/Users";
import AuditLog from "./pages/AuditLog";
import Settings from "./pages/Settings";
import AdminConsole from "./pages/AdminConsole";
import DashboardLayout from "./components/DashboardLayout";
import ForceChangePassword from "./pages/ForceChangePassword";

const ProtectedRoute = ({ children, allowedRoles }) => {
  const { user, isLoading } = useAuth();
  const location = useLocation();
  
  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Cargando...</div>
      </div>
    );
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (user.must_change_password && location.pathname !== "/force-change-password") {
    return <Navigate to="/force-change-password" replace />;
  }

  if (!user.must_change_password && location.pathname === "/force-change-password") {
    return <Navigate to="/dashboard" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }
  
  return children;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          
          <Route path="/force-change-password" element={
            <ProtectedRoute>
              <ForceChangePassword />
            </ProtectedRoute>
          } />

          <Route path="/dashboard" element={
            <ProtectedRoute>
              <DashboardLayout>
                <Dashboard />
              </DashboardLayout>
            </ProtectedRoute>
          } />
          
          <Route path="/budgets" element={
            <ProtectedRoute allowedRoles={["admin", "finanzas"]}>
              <DashboardLayout>
                <Budgets />
              </DashboardLayout>
            </ProtectedRoute>
          } />
          
          <Route path="/movements" element={
            <ProtectedRoute allowedRoles={["admin", "finanzas", "captura_ingresos"]}>
              <DashboardLayout>
                <Movements />
              </DashboardLayout>
            </ProtectedRoute>
          } />
          
          <Route path="/authorizations" element={
            <ProtectedRoute allowedRoles={["admin", "autorizador"]}>
              <DashboardLayout>
                <Authorizations />
              </DashboardLayout>
            </ProtectedRoute>
          } />
          
          <Route path="/reports" element={
            <ProtectedRoute>
              <DashboardLayout>
                <Reports />
              </DashboardLayout>
            </ProtectedRoute>
          } />
          
          <Route path="/catalogs" element={
            <ProtectedRoute allowedRoles={["admin", "finanzas"]}>
              <DashboardLayout>
                <Catalogs />
              </DashboardLayout>
            </ProtectedRoute>
          } />
          
          <Route path="/users" element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <DashboardLayout>
                <Users />
              </DashboardLayout>
            </ProtectedRoute>
          } />
          
          <Route path="/audit" element={
            <ProtectedRoute allowedRoles={["admin", "autorizador"]}>
              <DashboardLayout>
                <AuditLog />
              </DashboardLayout>
            </ProtectedRoute>
          } />
          
          <Route path="/admin" element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <DashboardLayout>
                <AdminConsole />
              </DashboardLayout>
            </ProtectedRoute>
          } />
          
          <Route path="/settings" element={
            <ProtectedRoute>
              <DashboardLayout>
                <Settings />
              </DashboardLayout>
            </ProtectedRoute>
          } />
        </Routes>
        <Toaster position="top-right" richColors />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
