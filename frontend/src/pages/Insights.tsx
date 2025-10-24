import React, { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function Insights() {
  const [metrics, setMetrics] = useState({
    accuracy: 0,
    precision: 0,
    recall: 0,
    f1: 0,
  });

  const [confusionMatrix, setConfusionMatrix] = useState([
    [0, 0],
    [0, 0],
  ]);

  const [trafficData, setTrafficData] = useState([
    { name: "Normal", count: 0 },
    { name: "Attack", count: 0 },
  ]);

  useEffect(() => {
    // Fetch metrics
    fetch("http://127.0.0.1:5000/insights/metrics")
      .then((res) => res.json())
      .then((data) => setMetrics(data))
      .catch(console.error);

    // Fetch confusion matrix
    fetch("http://127.0.0.1:5000/insights/confusion")
      .then((res) => res.json())
      .then((data) => setConfusionMatrix(data))
      .catch(console.error);

    // Fetch traffic / normal vs attack counts
    fetch("http://127.0.0.1:5000/insights/traffic")
      .then((res) => res.json())
      .then((data) => setTrafficData(data))
      .catch(console.error);
  }, []);

  return (
    <div className="space-y-6">
      {/* Model Performance */}
      <Card className="border-border bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-foreground">Model Performance</CardTitle>
          <p className="text-sm text-muted-foreground mt-1">Real-time ML model metrics</p>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-lg bg-gradient-cyber border border-primary/30">
              <p className="text-sm text-muted-foreground mb-1">Accuracy</p>
              <p className="text-2xl font-bold text-foreground">{metrics.accuracy}%</p>
            </div>
            <div className="p-4 rounded-lg bg-gradient-cyber border border-primary/30">
              <p className="text-sm text-muted-foreground mb-1">Precision</p>
              <p className="text-2xl font-bold text-foreground">{metrics.precision}%</p>
            </div>
            <div className="p-4 rounded-lg bg-gradient-cyber border border-primary/30">
              <p className="text-sm text-muted-foreground mb-1">Recall</p>
              <p className="text-2xl font-bold text-foreground">{metrics.recall}%</p>
            </div>
            <div className="p-4 rounded-lg bg-gradient-cyber border border-primary/30">
              <p className="text-sm text-muted-foreground mb-1">F1 Score</p>
              <p className="text-2xl font-bold text-foreground">{metrics.f1}%</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Confusion Matrix */}
      <Card className="border-border bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-foreground">Confusion Matrix</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-2 text-sm">
              <div></div>
              <div className="text-center font-medium text-muted-foreground">Predicted Normal</div>
              <div className="text-center font-medium text-muted-foreground">Predicted Malicious</div>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="flex items-center font-medium text-muted-foreground text-sm">Actual Normal</div>
              <div className="bg-success/20 border border-success/30 rounded-lg p-6 text-center">
                <span className="text-2xl font-bold text-foreground">{confusionMatrix[0][0]}</span>
              </div>
              <div className="bg-destructive/20 border border-destructive/30 rounded-lg p-6 text-center">
                <span className="text-2xl font-bold text-foreground">{confusionMatrix[0][1]}</span>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="flex items-center font-medium text-muted-foreground text-sm">Actual Malicious</div>
              <div className="bg-destructive/20 border border-destructive/30 rounded-lg p-6 text-center">
                <span className="text-2xl font-bold text-foreground">{confusionMatrix[1][0]}</span>
              </div>
              <div className="bg-success/20 border border-success/30 rounded-lg p-6 text-center">
                <span className="text-2xl font-bold text-foreground">{confusionMatrix[1][1]}</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Traffic Insights */}
      <Card className="border-border bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-foreground">Traffic Insights</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={trafficData}>
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="count" fill="#2563eb" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}
