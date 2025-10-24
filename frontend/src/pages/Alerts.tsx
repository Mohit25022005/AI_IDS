import React, { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AlertTriangle, CheckCircle, XCircle } from "lucide-react";
import { api } from "@/lib/api";

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);

  const fetchAlerts = async () => {
    try {
      const res = await api.get("/alerts");
      setAlerts(res.data);
    } catch (err) {
      console.error("Error fetching alerts:", err);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, []);

  const getSeverityColor = (severity) => {
    switch (severity) {
      case "critical": return "bg-destructive/20 text-destructive border-destructive/30";
      case "high": return "bg-warning/20 text-warning border-warning/30";
      case "medium": return "bg-chart-2/20 text-chart-2 border-chart-2/30";
      default: return "bg-muted text-muted-foreground border-border";
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case "active": return <AlertTriangle className="h-4 w-4 text-destructive" />;
      case "reviewed": return <CheckCircle className="h-4 w-4 text-success" />;
      case "false-positive": return <XCircle className="h-4 w-4 text-muted-foreground" />;
      default: return null;
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold mb-4">Threat Alerts</h1>
      <div className="space-y-4">
        {alerts.map((alert) => (
          <div
            key={alert.id}
            className="p-4 rounded-lg border border-border bg-background/50 hover:bg-secondary/20 transition-colors"
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                {getStatusIcon(alert.status)}
                <div>
                  <h3 className="font-semibold text-foreground">{alert.type}</h3>
                  <p className="text-xs text-muted-foreground">{alert.timestamp}</p>
                </div>
              </div>
              <Badge className={getSeverityColor(alert.severity)}>
                {alert.severity.toUpperCase()}
              </Badge>
            </div>
            <p className="text-sm text-foreground mb-3">{alert.description}</p>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Source:</span>
                <code className="text-xs font-mono text-primary bg-primary/10 px-2 py-1 rounded">{alert.sourceIP}</code>
              </div>
              <div className="flex gap-2">
                {alert.status === "active" && (
                  <>
                    <Button size="sm" variant="outline">Mark as Reviewed</Button>
                    <Button size="sm" variant="outline">False Positive</Button>
                  </>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
