import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { createApiClient } from "../lib/http";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem("token"));
  const [isLoading, setIsLoading] = useState(true);

  const api = useCallback(() => createApiClient(token), [token]);

  useEffect(() => {
    const checkAuth = async () => {
      if (token) {
        try {
          const response = await api().get("/auth/me");
          setUser(response.data);
        } catch (error) {
          console.error("Auth check failed:", error);
          localStorage.removeItem("token");
          setToken(null);
          setUser(null);
        }
      }
      setIsLoading(false);
    };
    checkAuth();
  }, [token, api]);

  const login = async (email, password) => {
    const response = await createApiClient().post("/auth/login", { email, password });
    const { access_token, user: userData } = response.data;
    localStorage.setItem("token", access_token);
    setToken(access_token);
    setUser(userData);
    return response.data;
  };

  const changePassword = async (current_password, new_password) => {
    const response = await api().post("/auth/change-password", { current_password, new_password });
    const { access_token, user: userData } = response.data;
    localStorage.setItem("token", access_token);
    setToken(access_token);
    setUser(userData);
    return response.data;
  };

  const forceChangePassword = async (new_password) => {
    const response = await api().post("/auth/force-change-password", { new_password });
    const { access_token, user: userData } = response.data;
    localStorage.setItem("token", access_token);
    setToken(access_token);
    setUser(userData);
    return response.data;
  };

  const logout = () => {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
  };

  const hasRole = (...roles) => user && roles.includes(user.role);

  const canEdit = () => hasRole("admin", "finanzas");
  const canAuthorize = () => hasRole("admin", "autorizador");
  const canManage = () => hasRole("admin");

  return (
    <AuthContext.Provider value={{
      user,
      token,
      isLoading,
      login,
      logout,
      api,
      hasRole,
      canEdit,
      canAuthorize,
      canManage,
      changePassword,
      forceChangePassword,
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
};
