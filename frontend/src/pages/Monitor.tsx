import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
import { predictIntrusion, api } from "@/lib/api";

export default function Monitor() {
  const [features, setFeatures] = useState("");
  const [url, setUrl] = useState("");
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const { toast } = useToast();

  // Fetch prediction history
  const fetchHistory = async () => {
    try {
      const res = await api.get("/monitor/history");
      setHistory(res.data);
    } catch (err) {
      console.error("Error fetching history:", err);
    }
  };

  // Fetch alerts
  const fetchAlerts = async () => {
    try {
      const res = await api.get("/alerts");
      setAlerts(res.data);
    } catch (err) {
      console.error("Error fetching alerts:", err);
    }
  };

  useEffect(() => {
    fetchHistory();
    fetchAlerts();
    const interval = setInterval(() => {
      fetchHistory();
      fetchAlerts();
    }, 5000); // update every 5s
    return () => clearInterval(interval);
  }, []);

  const handlePredict = async () => {
    try {
      let payload;

      if (features) {
        // Mode 1: direct feature input
        const featureArray = features.split(",").map(Number);
        payload = { features: featureArray };
      } else if (url) {
        // Mode 2: URL input
        payload = { url: url.trim() };
      } else {
        toast({
          variant: "destructive",
          title: "Error",
          description: "Please enter either features or a URL",
        });
        return;
      }

      const res = await api.post("/predict", payload);
      setResult(res.data.prediction);

      toast({
        title: "Prediction Successful",
        description: `Result: ${res.data.prediction.toUpperCase()} (Confidence: ${(res.data.confidence*100).toFixed(1)}%)`,
      });

      fetchHistory();
      fetchAlerts();
    } catch (err) {
      console.error(err);
      const errorMsg = err.response?.data?.error || "Unable to connect to the backend API.";
      toast({
        variant: "destructive",
        title: "Error",
        description: errorMsg,
      });
    }
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-semibold">Network Monitor</h1>

      <div>
        <p>Enter NSL-KDD feature values (comma-separated):</p>
        <Input
          value={features}
          onChange={(e) => setFeatures(e.target.value)}
          placeholder="0,0,1,0,181,5450,..."
        />
      </div>

      <div className="mt-4">
        <p>Or enter a URL to analyze network traffic:</p>
        <Input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.example.com"
        />
      </div>

      <Button className="mt-4" onClick={handlePredict}>
        Predict
      </Button>

      {result && (
        <div className="p-4 border rounded-lg mt-4">
          <h2 className="font-bold text-lg">
            🧠 Prediction:{" "}
            <span className={result === "attack" ? "text-red-600" : "text-green-600"}>
              {result.toUpperCase()}
            </span>
          </h2>
        </div>
      )}

      {/* Prediction History Table */}
      <div className="overflow-x-auto mt-6">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Timestamp</th>
              <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Prediction</th>
              <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {history.map((item, idx) => (
              <tr key={idx} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                <td className="py-3 px-4 text-sm text-foreground">{item.timestamp}</td>
                <td className={`py-3 px-4 text-sm font-bold ${item.prediction === "attack" ? "text-red-600" : "text-green-600"}`}>
                  {item.prediction.toUpperCase()}
                </td>
                <td className="py-3 px-4 text-sm text-foreground">{(item.confidence * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Alerts */}
      <div className="mt-6">
        <h2 className="text-xl font-semibold">Alerts</h2>
        <ul className="space-y-2 mt-2">
          {alerts.length ? alerts.map((alert) => (
            <li key={alert.id} className="p-3 border rounded-lg bg-black-50 border-red-200">
              <p className="font-bold">{alert.type}</p>
              <p>{alert.description}</p>
              <p className="text-sm text-muted-foreground">{alert.timestamp}</p>
            </li>
          )) : <p className="text-sm text-muted-foreground">No active alerts</p>}
        </ul>
      </div>
    </div>
  );
}
