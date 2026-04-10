import axios from "axios";

const API_BASE_URL = "http://127.0.0.1:5000";

// ---------------- Axios Instance ----------------
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// ---------------- Global Error Handler ----------------
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error("API Error:", error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// ---------------- Types ----------------
export interface PredictionResponse {
  prediction: string;
  confidence: number;
  timestamp: string;
  features_named?: Record<string, number>;
  interpreted?: {
    traffic_volume: number;
    connection_count: number;
    service_match_rate: number;
  };
}

// ---------------- Prediction APIs ----------------

// 🔹 Predict using features
export const predictWithFeatures = async (features: number[]): Promise<PredictionResponse> => {
  const res = await api.post("/predict", { features });
  return res.data;
};

// 🔹 Predict using URL
export const predictWithURL = async (url: string): Promise<PredictionResponse> => {
  const res = await api.post("/predict", { url });
  return res.data;
};

// ---------------- Monitoring APIs ----------------

// 🔹 Get prediction history
export const getHistory = async () => {
  const res = await api.get("/monitor/history");
  return res.data;
};

// 🔹 Get alerts
export const getAlerts = async () => {
  const res = await api.get("/alerts");
  return res.data;
};

// 🔹 Backend health check
export const checkServer = async () => {
  const res = await api.get("/");
  return res.data;
};