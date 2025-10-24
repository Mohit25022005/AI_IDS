import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
import { predictIntrusion, api } from "@/lib/api";

export default function Monitor() {
  const [features, setFeatures] = useState("");
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const { toast } = useToast();

  // Fetch prediction history from backend
  const fetchHistory = async () => {
    try {
      const res = await api.get("/monitor/history");
      setHistory(res.data);
    } catch (err) {
      console.error("Error fetching history:", err);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handlePredict = async () => {
    try {
      const featureArray = features.split(",").map(Number);
      const res = await predictIntrusion(featureArray);
      setResult(res.prediction);
      toast({
        title: "Prediction Successful",
        description: `Result: ${res.prediction.toUpperCase()}`,
      });
      fetchHistory(); // Refresh history after prediction
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Error",
        description: "Unable to connect to the backend API.",
      });
      console.error(err);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-semibold">Network Monitor</h1>
      <p>Enter NSL-KDD feature values separated by commas:</p>
      <div className="flex gap-2">
        <Input
          value={features}
          onChange={(e) => setFeatures(e.target.value)}
          placeholder="e.g. 0,0,1,0,181,5450,0,..."
        />
        <Button onClick={handlePredict}>Predict</Button>
      </div>

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
    </div>
  );
}
