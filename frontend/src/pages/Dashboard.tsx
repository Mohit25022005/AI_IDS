import { useEffect, useState } from "react";
import { Shield, Activity, AlertTriangle, TrendingUp, Clock, Zap } from "lucide-react";
import MetricCard from "@/components/MetricCard";
import TrafficChart from "@/components/TrafficChart";
import ThreatDistribution from "@/components/ThreatDistribution";
import { api } from "@/lib/api";

interface Metrics {
  flowsAnalyzed: number;
  normalFlows: number;
  attackFlows: number;
  attackRate: string;
  activeAlerts: number;
  systemStatus: string;
  avgLatencyMs: string;
  activeModel: string;
}

const DEFAULT_METRICS: Metrics = {
  flowsAnalyzed: 0,
  normalFlows: 0,
  attackFlows: 0,
  attackRate: "0.00%",
  activeAlerts: 0,
  systemStatus: "Safe",
  avgLatencyMs: "—",
  activeModel: "—",
};

export default function Dashboard() {
  const [metrics, setMetrics] = useState<Metrics>(DEFAULT_METRICS);

  const fetchDashboard = async () => {
    try {
      const [histRes, alertsRes] = await Promise.all([
        api.get("/monitor/history?limit=1&page=1"),
        api.get("/alerts?limit=1&page=1"),
      ]);

      const h = histRes.data;
      const a = alertsRes.data;

      const activeAlerts: number = (a.alerts ?? []).filter(
        (al: { status: string }) => al.status === "active"
      ).length;

      setMetrics({
        flowsAnalyzed: h.total_records ?? 0,
        normalFlows:   h.normal_count  ?? 0,
        attackFlows:   h.attack_count  ?? 0,
        attackRate:    `${h.attack_rate ?? 0}%`,
        activeAlerts:  a.total > 0 ? a.total : 0,   // total alerts ever
        systemStatus:  (h.attack_count ?? 0) > 0 ? "Under Attack" : "Safe",
        avgLatencyMs:
          h.avg_latency_ms != null ? `${h.avg_latency_ms} ms` : "—",
        activeModel: h.active_model ?? "—",
      });
    } catch {
      // backend not reachable — leave last known values
    }
  };

  useEffect(() => {
    fetchDashboard();
    const id = setInterval(fetchDashboard, 3000);
    return () => clearInterval(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-6">
      {/* KPI cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <MetricCard
          title="Flows Analyzed"
          value={metrics.flowsAnalyzed}
          icon={Activity}
          variant="default"
        />
        <MetricCard
          title="Normal Flows"
          value={metrics.normalFlows}
          icon={Shield}
          variant="success"
        />
        <MetricCard
          title="Attack Flows"
          value={metrics.attackFlows}
          icon={AlertTriangle}
          variant="danger"
        />
        <MetricCard
          title="Attack Rate"
          value={metrics.attackRate}
          icon={TrendingUp}
          variant={parseFloat(metrics.attackRate) > 0 ? "danger" : "success"}
        />
        <MetricCard
          title="Avg Latency"
          value={metrics.avgLatencyMs}
          icon={Clock}
          variant="default"
        />
        <MetricCard
          title="System Status"
          value={metrics.systemStatus}
          icon={Zap}
          variant={metrics.systemStatus === "Safe" ? "success" : "danger"}
        />
      </div>

      {/* Active model badge */}
      {metrics.activeModel !== "—" && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="w-2 h-2 rounded-full bg-primary inline-block" />
          Active model: <span className="font-medium text-foreground">{metrics.activeModel}</span>
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TrafficChart />
        <ThreatDistribution />
      </div>
    </div>
  );
}
