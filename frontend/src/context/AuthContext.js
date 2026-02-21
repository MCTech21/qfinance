import { createContext, useContext, useState, useEffect, useCallback, useMemo } from "react";
import { createApiClient } from "../lib/http";

const AuthContext = createContext(null);

const parseJwtClaims = (token) => {
  if (!token) return {};
  try {
    const payload = token.split(".")[1];
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(normalized));
  } catch {
    return {};
  }
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem("token"));
  const [isLoading, setIsLoading] = useState(true);
  const [allowedCompanies, setAllowedCompanies] = useState([]);

  const api = useCallback(() => createApiClient(token), [token]);
  const tokenClaims = useMemo(() => parseJwtClaims(token), [token]);

  const loadAllowedCompanies = useCallback(async (authToken = token) => {
    if (!authToken) return;
    try {
      const response = await createApiClient(authToken).get("/auth/allowed-companies");
      setAllowedCompanies(response.data || []);
    } catch {
      setAllowedCompanies([]);
    }
  }, [token]);

  const refreshMe = useCallback(async (authToken = token) => {
    if (!authToken) return null;
    const response = await createApiClient(authToken).get("/auth/me");
    setUser(response.data);
    return response.data;
  }, [token]);

  useEffect(() => {
    const checkAuth = async () => {
      if (token) {
        try {
          await refreshMe(token);
          await loadAllowedCompanies(token);
        } catch (error) {
          console.error("Auth check failed:", error);
          localStorage.removeItem("token");
          setToken(null);
          setUser(null);
          setAllowedCompanies([]);
        }
      }
      setIsLoading(false);
    };
    checkAuth();
  }, [token, refreshMe, loadAllowedCompanies]);

  const login = async (email, password) => {
    const response = await createApiClient().post("/auth/login", { email, password });
    const { access_token, user: userData } = response.data;
    localStorage.setItem("token", access_token);
    setToken(access_token);
    setUser(userData);
    await loadAllowedCompanies(access_token);
    return response.data;
  };

  const selectCompany = async (empresa_id) => {
    const response = await api().post("/auth/select-company", { empresa_id });
    const { access_token } = response.data;
    localStorage.setItem("token", access_token);
    setToken(access_token);
    await refreshMe(access_token);
    await loadAllowedCompanies(access_token);
    return response.data;
  };

  const changePassword = async (current_password, new_password) => {
    const response = await api().post("/auth/change-password", { current_password, new_password });
    const { access_token, user: userData } = response.data;
    localStorage.setItem("token", access_token);
    setToken(access_token);
    setUser(userData);
    await loadAllowedCompanies(access_token);
    return response.data;
  };

  const forceChangePassword = async (new_password) => {
    const response = await api().post("/auth/force-change-password", { new_password });
    const { access_token, user: userData } = response.data;
    localStorage.setItem("token", access_token);
    setToken(access_token);
    setUser(userData);
    await loadAllowedCompanies(access_token);
    return response.data;
  };

  const logout = () => {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
    setAllowedCompanies([]);
  };

  const hasRole = (...roles) => user && roles.includes(user.role);

  const canEdit = () => hasRole("admin", "finanzas");
  const canAuthorize = () => hasRole("admin", "autorizador");
  const canManage = () => hasRole("admin");

  return (
    <AuthContext.Provider value={{
      user,
      token,
      tokenClaims,
      allowedCompanies,
      isLoading,
      login,
      logout,
      api,
      selectCompany,
      refreshMe,
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
