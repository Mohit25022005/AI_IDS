import React, { useEffect, useState } from "react";
import { Shield, Activity, AlertTriangle, TrendingUp, Radar } from "lucide-react";
import MetricCard from "@/components/MetricCard";
import TrafficChart from "@/components/TrafficChart";
import ThreatDistribution from "@/components/ThreatDistribution";
import { api } from "@/lib/api";
import { getHistory, getAlerts } from "@/lib/api";

export default function Dashboard() {
  const [metrics, setMetrics] = useState({
    packetsAnalyzed: "0",
    threatsDetected: "0",
    modelAccuracy: "0%",
    systemStatus: "Safe",
    packetTrend: "+0%",
    threatTrend: "+0",
    accuracyTrend: "+0%",
  });

  const [trafficData, setTrafficData] = useState([]);
  const [threatData, setThreatData] = useState([]);

  const [latestPrediction, setLatestPrediction] = useState(null);
  const [insights, setInsights] = useState(null);

  const fetchDashboard = async () => {
    try {
      const history = await getHistory();
      const alerts = await getAlerts();

      const packetsAnalyzed = history.length;
      const threatsDetected = alerts.length;
      const attacks = history.filter(h => h.prediction === "attack").length;

      const accuracy =
        packetsAnalyzed > 0
          ? ((packetsAnalyzed - attacks) / packetsAnalyzed) * 100
          : 0;

      const systemStatus = attacks > 0 ? "Under Attack" : "Safe";

      setMetrics({
        packetsAnalyzed,
        threatsDetected,
        modelAccuracy: `${accuracy.toFixed(1)}%`,
        systemStatus,
        packetTrend: "+0%",
        threatTrend: `+${threatsDetected}`,
        accuracyTrend: "+0%",
      });

      // Charts
      setTrafficData([
        { name: "Normal", count: packetsAnalyzed - attacks },
        { name: "Attack", count: attacks },
      ]);

      setThreatData(alerts);

      // 🔥 NEW: Get latest prediction (from history)
      if (history.length > 0) {
        const last = history[history.length - 1];
        setLatestPrediction(last);
      }

      // 🔥 OPTIONAL: Fetch live prediction (for insights)
      try {
        const live = await api.post("/predict", {
          features: Array(41).fill(0) // dummy trigger
        });

        setInsights(live.data.interpreted);
      } catch (e) {
        // ignore if not needed
      }

    } catch (err) {
      console.error("Dashboard error:", err);
    }
  };

  useEffect(() => {
    fetchDashboard();
    const interval = setInterval(fetchDashboard, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">

      {/* 🔹 Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Packets Analyzed"
          value={metrics.packetsAnalyzed}
          icon={Activity}
          trend={metrics.packetTrend}
        />
        <MetricCard
          title="Threats Detected"
          value={metrics.threatsDetected}
          icon={AlertTriangle}
          trend={metrics.threatTrend}
          variant="danger"
        />
        <MetricCard
          title="Model Accuracy"
          value={metrics.modelAccuracy}
          icon={TrendingUp}
          trend={metrics.accuracyTrend}
          variant="success"
        />
        <MetricCard
          title="System Status"
          value={metrics.systemStatus}
          icon={Shield}
          variant={metrics.systemStatus === "Safe" ? "success" : "danger"}
        />
      </div>

      {/* 🔥 NEW: Live Prediction */}
      {latestPrediction && (
        <div className="bg-card p-6 rounded-2xl shadow">
          <h2 className="text-lg font-semibold mb-2">Live Prediction</h2>
          <div className="flex justify-between items-center">
            <div>
              <p className="text-2xl font-bold capitalize">
                {latestPrediction.prediction}
              </p>
              <p className="text-sm text-muted-foreground">
                Confidence: {(latestPrediction.confidence * 100).toFixed(1)}%
              </p>
            </div>
            <Radar className="w-10 h-10 text-primary" />
          </div>
        </div>
      )}

      {/* 🔥 NEW: Insights */}
      {insights && (
        <div className="bg-card p-6 rounded-2xl shadow">
          <h2 className="text-lg font-semibold mb-4">Network Insights</h2>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-xl font-bold">{insights.traffic_volume}</p>
              <p className="text-sm text-muted-foreground">Traffic Volume</p>
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

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TrafficChart data={trafficData} />
        <ThreatDistribution data={threatData} />
      </div>

    </div>
  );
}