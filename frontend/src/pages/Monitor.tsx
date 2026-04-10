import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";

import {
  predictWithFeatures,
  predictWithURL,
  getHistory,
  getAlerts,
  PredictionResponse,
} from "@/lib/api";

export default function Monitor() {
  const [features, setFeatures] = useState("");
  const [url, setUrl] = useState("");

  const [result, setResult] = useState<string | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [insights, setInsights] = useState<any>(null);

  // 🔥 NEW: Feature breakdown
  const [featureMap, setFeatureMap] = useState<Record<string, number> | null>(null);

  const [history, setHistory] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);

  const { toast } = useToast();

  // ---------------- Fetch Data ----------------
  const fetchHistory = async () => {
    try {
      const data = await getHistory();
      setHistory(data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchAlerts = async () => {
    try {
      const data = await getAlerts();
      setAlerts(data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchHistory();
    fetchAlerts();

    const interval = setInterval(() => {
      fetchHistory();
      fetchAlerts();
    }, 4000);

    return () => clearInterval(interval);
  }, []);

  // ---------------- Prediction ----------------
  const handlePredict = async () => {
    try {
      let res: PredictionResponse;

      if (features) {
        res = await predictWithFeatures(features.split(",").map(Number));
      } else if (url) {
        res = await predictWithURL(url.trim());
      } else {
        toast({
          variant: "destructive",
          title: "Error",
          description: "Enter features or URL",
        });
        return;
      }

      setResult(res.prediction);
      setConfidence(res.confidence);
      setInsights(res.interpreted);

      // 🔥 IMPORTANT: store feature breakdown
      setFeatureMap(res.features_named || null);

      toast({
        title: "Prediction Complete",
        description: `${res.prediction.toUpperCase()} (${(res.confidence * 100).toFixed(1)}%)`,
      });

      fetchHistory();
      fetchAlerts();

    } catch (err: any) {
      const errorMsg = err.response?.data?.error || "Backend error";
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

      {/* Inputs */}
      <div>
        <p>Enter NSL-KDD features:</p>
        <Input
          value={features}
          onChange={(e) => setFeatures(e.target.value)}
          placeholder="0,0,1,0,181,5450,..."
        />
      </div>

      <div>
        <p>Or enter URL:</p>
        <Input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com"
        />
      </div>

      <Button onClick={handlePredict}>Analyze Traffic</Button>

      {/* Result */}
      {result && confidence !== null && (
        <div className="p-5 rounded-2xl shadow bg-card">
          <h2 className="text-lg font-semibold mb-2">Live Analysis</h2>

          <p className={`text-2xl font-bold ${result === "attack" ? "text-red-600" : "text-green-600"}`}>
            {result.toUpperCase()}
          </p>

          <p className="text-sm text-muted-foreground">
            Confidence: {(confidence * 100).toFixed(1)}%
          </p>
        </div>
      )}

      {/* Insights */}
      {insights && (
        <div className="p-5 rounded-2xl shadow bg-card">
          <h2 className="text-lg font-semibold mb-4">Network Insights</h2>

          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-xl font-bold">{insights.traffic_volume}</p>
              <p className="text-sm text-muted-foreground">Traffic</p>
            </div>

            <div>
              <p className="text-xl font-bold">{insights.connection_count}</p>
              <p className="text-sm text-muted-foreground">Connections</p>
            </div>

            <div>
              <p className="text-xl font-bold">
                {(insights.service_match_rate * 100).toFixed(1)}%
              </p>
              <p className="text-sm text-muted-foreground">Service Match</p>
            </div>
          </div>
        </div>
      )}

      {/* 🔥 NEW: Feature Breakdown */}
      {featureMap && (
        <div className="p-5 rounded-2xl shadow bg-card">
          <h2 className="text-lg font-semibold mb-4">
            🔍 Extracted Features (URL → KDD)
          </h2>

          <div className="max-h-80 overflow-y-auto border rounded-lg">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-muted">
                <tr>
                  <th className="text-left px-3 py-2">Feature</th>
                  <th className="text-left px-3 py-2">Value</th>
                </tr>
              </thead>

              <tbody>
                {Object.entries(featureMap).map(([key, value]) => (
                  <tr key={key} className="border-t hover:bg-muted/30">
                    <td className="px-3 py-2 font-medium">{key}</td>
                    <td
                      className={`px-3 py-2 ${
                        value > 1000 ? "text-red-500 font-bold" : "text-muted-foreground"
                      }`}
                    >
                      {typeof value === "number" ? value.toFixed(2) : value}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* History */}
      <div className="overflow-x-auto">
        <h2 className="text-xl font-semibold mb-2">Prediction History</h2>
        <table className="w-full">
          <thead>
            <tr>
              <th>Time</th>
              <th>Prediction</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {history.map((h, i) => (
              <tr key={i}>
                <td>{h.timestamp}</td>
                <td className={h.prediction === "attack" ? "text-red-600" : "text-green-600"}>
                  {h.prediction}
                </td>
                <td>{(h.confidence * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Alerts */}
      <div>
        <h2 className="text-xl font-semibold">Alerts</h2>

        {alerts.length === 0 ? (
          <p className="text-muted-foreground">No alerts</p>
        ) : (
          alerts.map((a) => (
            <div key={a.id} className="p-4 border rounded-lg bg-red-50 mt-2">
              <p className="font-bold text-red-600">{a.type}</p>
              <p>{a.description}</p>
              <p className="text-sm text-muted-foreground">{a.timestamp}</p>
            </div>
          ))
        )}
      </div>

    </div>
  );
}