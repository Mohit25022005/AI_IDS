import axios from "axios";

const API_BASE_URL = "http://127.0.0.1:5000"; // Flask backend

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Example: Send feature array to backend
export const predictIntrusion = async (features) => {
  const response = await api.post("/predict", { features });
  return response.data;
};

// Example: Check backend status
export const checkServer = async () => {
  const response = await api.get("/");
  return response.data;
};
