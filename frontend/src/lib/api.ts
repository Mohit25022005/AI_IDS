import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:5000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

/** Inject API key header when VITE_API_KEY is set */
api.interceptors.request.use((config) => {
  const key = import.meta.env.VITE_API_KEY;
  if (key) config.headers["X-API-Key"] = key;
  return config;
});

export const predictIntrusion = async (features: Record<string, number | string>) => {
  const res = await api.post("/predict", { features });
  return res.data;
};

export const checkServer = async () => {
  const res = await api.get("/");
  return res.data;
};
