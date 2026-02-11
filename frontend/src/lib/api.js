const rawBackendUrl = process.env.REACT_APP_BACKEND_URL;

const normalizeBackendUrl = (url) => {
  if (!url) {
    return "";
  }

  const trimmed = url.trim();
  if (!trimmed) {
    return "";
  }

  return trimmed.replace(/\/+$/, "");
};

const backendUrl = normalizeBackendUrl(rawBackendUrl);

export const API_BASE_URL = backendUrl ? `${backendUrl}/api` : "/api";

export const withApiPath = (path) => {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
};
