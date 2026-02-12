import axios from "axios";
import { API_BASE_URL } from "./api";

export const createApiClient = (token) => {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  return axios.create({
    baseURL: API_BASE_URL,
    headers,
    withCredentials: false,
    timeout: 15000,
  });
};
