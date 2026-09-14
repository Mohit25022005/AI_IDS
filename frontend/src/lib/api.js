import axios from "axios";

const API_BASE_URL = "http://127.0.0.1:5000"; // Flask backend

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Send 27 live-flow features to the backend
export const predictIntrusion = async (features) => {
  if (!features || typeof features !== "object" || Array.isArray(features)) {
    throw new Error("Features must be provided as an object");
  }

  const response = await api.post("/predict", {
    features,
  });

  return response.data;
};

// Example: Check backend status
export const checkServer = async () => {
  const response = await api.get("/");
  return response.data;
};
