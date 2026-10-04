import React, { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronUp,
  Wifi,
  WifiOff,
  Brain,
  Activity,
} from "lucide-react";
import { api } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────
interface ShapEntry {
  feature: string;
  contribution: number;
}

interface Alert {
  id: string;
  event_id: string;
  timestamp: string;
  type: string;
  severity: string;
  sourceIP: string;
  destinationIP: string;
  sourcePort: number;
  destinationPort: number;
  protocol: string;
  confidence: number;
  latency_ms: number;
  model_used: string;
  description: string;
  status: string;
  anomaly_score: number | null;
  shap_top5: ShapEntry[];
}

// ── Helpers ───────────────────────────────────────────────────────────
const API_BASE = (import.meta.env.VITE_API_URL ?? "http://127.0.0.1:5000") as string;

function getSeverityColor(severity: string) {
  switch (severity) {
    case "critical": return "bg-destructive/20 text-destructive border-destructive/30";
    case "high":     return "bg-warning/20 text-warning border-warning/30";
    case "medium":   return "bg-chart-2/20 text-chart-2 border-chart-2/30";
    default:         return "bg-muted text-muted-foreground border-border";
  }
}

function getStatusIcon(status: string) {
  switch (status) {
    case "active":         return <AlertTriangle className="h-4 w-4 text-destructive" />;
    case "reviewed":       return <CheckCircle   className="h-4 w-4 text-green-500" />;
    case "false-positive": return <XCircle       className="h-4 w-4 text-muted-foreground" />;
    default:               return null;
  }
}

function AnomalyBar({ score }: { score: number | null }) {
  if (score === null || score === undefined) return null;
  const pct = Math.round(score * 100);
  const color =
    pct >= 75 ? "bg-destructive" :
    pct >= 50 ? "bg-warning" :
    "bg-green-500";
  return (
    <div className="flex items-center gap-2 mt-1">
      <Activity className="h-3 w-3 text-muted-foreground shrink-0" />
      <span className="text-xs text-muted-foreground w-20 shrink-0">Anomaly:</span>
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-foreground w-8 text-right">{pct}%</span>
    </div>
  );
}

function ShapChart({ entries }: { entries: ShapEntry[] }) {
  if (!entries || entries.length === 0) return null;
  const maxAbs = Math.max(...entries.map(e => Math.abs(e.contribution)), 0.001);
  return (
    <div className="mt-3 space-y-1">
      <p className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
        <Brain className="h-3 w-3" /> Top feature contributions (SHAP)
      </p>
      {entries.map((e) => {
        const pct  = Math.round((Math.abs(e.contribution) / maxAbs) * 100);
        const positive = e.contribution >= 0;
        return (
          <div key={e.feature} className="flex items-center gap-2">
            <span className="text-xs font-mono text-muted-foreground w-36 truncate shrink-0">
              {e.feature}
            </span>
            <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full ${positive ? "bg-destructive" : "bg-blue-400"}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className={`text-xs font-mono w-14 text-right ${positive ? "text-destructive" : "text-blue-400"}`}>
              {e.contribution > 0 ? "+" : ""}{e.contribution.toFixed(4)}
            </span>
          </div>
        );
      })}
      <p className="text-xs text-muted-foreground mt-0.5">
        Red = pushes toward attack · Blue = pushes toward normal
      </p>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────
export default function Alerts() {
  const [alerts, setAlerts]           = useState<Alert[]>([]);
  const [connected, setConnected]     = useState(false);
  const [expanded, setExpanded]       = useState<Set<string>>(new Set());
  const [filterSeverity, setFilterSeverity] = useState("");
  const [filterStatus, setFilterStatus]     = useState("");
  const esRef = useRef<EventSource | null>(null);

  // ── SSE connection ─────────────────────────────────────────────────
  const connectSSE = () => {
    if (esRef.current) {
      esRef.current.close();
    }

    const apiKey = import.meta.env.VITE_API_KEY;
    // EventSource doesn't support custom headers; pass key as query param
    const url = `${API_BASE}/stream/alerts${apiKey ? `?api_key=${apiKey}` : ""}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setConnected(true);
    };

    es.onmessage = (event) => {
      try {
        const alert: Alert = JSON.parse(event.data);
        setAlerts((prev) => {
          // Initial batch arrives as individual messages; dedup by id
          const exists = prev.some((a) => a.id === alert.id);
          if (exists) {
            // Update existing (e.g. status patch propagated)
            return prev.map((a) => (a.id === alert.id ? alert : a));
          }
          // Prepend new alert, cap at 200
          return [alert, ...prev].slice(0, 200);
        });
      } catch {
        // heartbeat comments arrive as empty data — safe to ignore
      }
    };

    es.onerror = () => {
      setConnected(false);
      es.close();
      // Reconnect after 5 seconds
      setTimeout(connectSSE, 5000);
    };
  };

  useEffect(() => {
    connectSSE();
    return () => {
      esRef.current?.close();
    };
  }, []);

  // ── Alert status update ────────────────────────────────────────────
  const updateAlertStatus = async (alertId: string, status: string) => {
    try {
      await api.patch(`/alerts/${alertId}`, { status });
      // Optimistic update
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, status } : a))
      );
    } catch (err: any) {
      console.error("Error updating alert:", err.response?.data?.error ?? err.message);
    }
  };

  // ── Toggle detail expansion ────────────────────────────────────────
  const toggleExpanded = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  // ── Filtered view ──────────────────────────────────────────────────
  const visible = alerts.filter((a) => {
    if (filterSeverity && a.severity !== filterSeverity) return false;
    if (filterStatus   && a.status   !== filterStatus)   return false;
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Threat Alerts</h1>
        <div className="flex items-center gap-2">
          {connected ? (
            <span className="flex items-center gap-1 text-xs text-green-500">
              <Wifi className="h-3 w-3" /> Live
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <WifiOff className="h-3 w-3" /> Reconnecting…
            </span>
          )}
          <span className="text-xs text-muted-foreground">
            {visible.length} alert{visible.length !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          className="text-xs px-2 py-1 rounded border border-border bg-background text-foreground"
          value={filterSeverity}
          onChange={(e) => setFilterSeverity(e.target.value)}
        >
          <option value="">All severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="info">Info</option>
        </select>
        <select
          className="text-xs px-2 py-1 rounded border border-border bg-background text-foreground"
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="reviewed">Reviewed</option>
          <option value="false-positive">False Positive</option>
          <option value="resolved">Resolved</option>
        </select>
      </div>

      {/* Alert list */}
      <div className="space-y-4">
        {visible.length === 0 && (
          <p className="text-sm text-muted-foreground py-8 text-center">
            No alerts match the current filters.
          </p>
        )}

        {visible.map((alert) => {
          const isExpanded = expanded.has(alert.id);
          const hasShap    = alert.shap_top5?.length > 0;
          const hasAnomaly = alert.anomaly_score !== null && alert.anomaly_score !== undefined;

          return (
            <div
              key={alert.id}
              className="p-4 rounded-lg border border-border bg-background/50 hover:bg-secondary/20 transition-colors"
            >
              {/* Top row */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  {getStatusIcon(alert.status)}
                  <div>
                    <h3 className="font-semibold text-foreground">{alert.type}</h3>
                    <p className="text-xs text-muted-foreground">{alert.timestamp}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge className={getSeverityColor(alert.severity)}>
                    {(alert.severity ?? "").toUpperCase()}
                  </Badge>
                  {(hasShap || hasAnomaly) && (
                    <button
                      onClick={() => toggleExpanded(alert.id)}
                      className="text-muted-foreground hover:text-foreground transition-colors"
                      aria-label="Toggle details"
                    >
                      {isExpanded
                        ? <ChevronUp  className="h-4 w-4" />
                        : <ChevronDown className="h-4 w-4" />}
                    </button>
                  )}
                </div>
              </div>

              {/* Description */}
              <p className="text-sm text-foreground mb-3">{alert.description}</p>

              {/* Anomaly bar (always visible if present) */}
              <AnomalyBar score={alert.anomaly_score} />

              {/* Expandable detail panel */}
              {isExpanded && (
                <div className="mt-3 pt-3 border-t border-border/50">
                  <ShapChart entries={alert.shap_top5} />
                </div>
              )}

              {/* Network details + actions */}
              <div className="flex items-center justify-between mt-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-muted-foreground">Source:</span>
                  <code className="text-xs font-mono text-primary bg-primary/10 px-2 py-1 rounded">
                    {alert.sourceIP || "N/A"}
                  </code>
                  <span className="text-xs text-muted-foreground">→ Dest:</span>
                  <code className="text-xs font-mono text-primary bg-primary/10 px-2 py-1 rounded">
                    {alert.destinationIP || "N/A"}
                  </code>
                  {alert.sourcePort !== undefined && (
                    <span className="text-xs text-muted-foreground">
                      Port:{" "}
                      <code className="font-mono text-foreground">
                        {alert.sourcePort} → {alert.destinationPort}
                      </code>
                    </span>
                  )}
                  {alert.protocol && (
                    <Badge variant="outline">{alert.protocol.toUpperCase()}</Badge>
                  )}
                  {alert.confidence !== undefined && (
                    <span className="text-xs text-muted-foreground">
                      Confidence:{" "}
                      <span className="font-semibold text-foreground">{alert.confidence}%</span>
                    </span>
                  )}
                </div>

                <div className="flex gap-2 shrink-0">
                  {alert.status === "active" && (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => updateAlertStatus(alert.id, "reviewed")}
                      >
                        Mark Reviewed
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => updateAlertStatus(alert.id, "false-positive")}
                      >
                        False Positive
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
