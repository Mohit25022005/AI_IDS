import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AlertTriangle, CheckCircle, XCircle } from "lucide-react";

const mockAlerts = [
  {
    id: 1,
    timestamp: "2025-01-15 10:23:49",
    type: "DDoS Attack",
    severity: "high",
    sourceIP: "203.0.113.15",
    description: "Unusual traffic pattern detected from multiple sources",
    status: "active",
  },
  {
    id: 2,
    timestamp: "2025-01-15 10:15:32",
    type: "Malware Signature",
    severity: "critical",
    sourceIP: "172.16.0.23",
    description: "Known malware signature detected in network traffic",
    status: "active",
  },
  {
    id: 3,
    timestamp: "2025-01-15 09:58:12",
    type: "Port Scan",
    severity: "medium",
    sourceIP: "192.168.1.105",
    description: "Sequential port scanning activity detected",
    status: "reviewed",
  },
  {
    id: 4,
    timestamp: "2025-01-15 09:42:07",
    type: "SQL Injection Attempt",
    severity: "high",
    sourceIP: "10.20.30.45",
    description: "Potential SQL injection in web request parameters",
    status: "false-positive",
  },
];

export default function Alerts() {
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "critical":
        return "bg-destructive/20 text-destructive border-destructive/30";
      case "high":
        return "bg-warning/20 text-warning border-warning/30";
      case "medium":
        return "bg-chart-2/20 text-chart-2 border-chart-2/30";
      default:
        return "bg-muted text-muted-foreground border-border";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "active":
        return <AlertTriangle className="h-4 w-4 text-destructive" />;
      case "reviewed":
        return <CheckCircle className="h-4 w-4 text-success" />;
      case "false-positive":
        return <XCircle className="h-4 w-4 text-muted-foreground" />;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      <Card className="border-border bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-foreground">Threat Alerts</CardTitle>
          <p className="text-sm text-muted-foreground">Real-time security threat notifications</p>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {mockAlerts.map((alert) => (
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
                    <code className="text-xs font-mono text-primary bg-primary/10 px-2 py-1 rounded">
                      {alert.sourceIP}
                    </code>
                  </div>
                  <div className="flex gap-2">
                    {alert.status === "active" && (
                      <>
                        <Button size="sm" variant="outline">
                          Mark as Reviewed
                        </Button>
                        <Button size="sm" variant="outline">
                          False Positive
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
