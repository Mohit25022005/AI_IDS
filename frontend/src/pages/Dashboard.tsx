import React, { useEffect, useState } from "react";
import { Shield, Activity, AlertTriangle, TrendingUp } from "lucide-react";
import MetricCard from "@/components/MetricCard";
import TrafficChart from "@/components/TrafficChart";
import ThreatDistribution from "@/components/ThreatDistribution";
import { api } from "@/lib/api";

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

  const fetchDashboard = async () => {
    try {
      // Fetch prediction history
      const historyRes = await api.get("/monitor/history");
      const history = historyRes.data;

      // Fetch alerts
      const alertsRes = await api.get("/alerts");
      const alerts = alertsRes.data;

      // Compute metrics
      const packetsAnalyzed = history.length;
      const threatsDetected = alerts.length;
      const attacks = history.filter(h => h.prediction === "attack").length;
      const accuracy =
        history.length > 0 ? ((packetsAnalyzed - attacks) / packetsAnalyzed) * 100 : 0;
      const systemStatus = threatsDetected > 0 ? "Under Attack" : "Safe";

      setMetrics({
        packetsAnalyzed,
        threatsDetected,
        modelAccuracy: `${accuracy.toFixed(1)}%`,
        systemStatus,
        packetTrend: "+0%", // optional: compute dynamically
        threatTrend: `+${threatsDetected}`,
        accuracyTrend: "+0%", // optional
      });

      // Traffic chart
      setTrafficData([
        { name: "Normal", count: history.filter(h => h.prediction === "normal").length },
        { name: "Attack", count: attacks },
      ]);

      // Threat distribution
      setThreatData(alerts);

    } catch (err) {
      console.error("Error fetching dashboard data:", err);
    }
  };

  useEffect(() => {
    fetchDashboard(); // initial fetch
    const interval = setInterval(fetchDashboard, 3000); // update every 3s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Packets Analyzed"
          value={metrics.packetsAnalyzed}
          icon={Activity}
          trend={metrics.packetTrend || "+0%"}
          variant="default"
        />
        <MetricCard
          title="Threats Detected"
          value={metrics.threatsDetected}
          icon={AlertTriangle}
          trend={metrics.threatTrend || "+0"}
          variant="danger"
        />
        <MetricCard
          title="Model Accuracy"
          value={metrics.modelAccuracy}
          icon={TrendingUp}
          trend={metrics.accuracyTrend || "+0%"}
          variant="success"
        />
        <MetricCard
          title="System Status"
          value={metrics.systemStatus}
          icon={Shield}
          variant={metrics.systemStatus === "Safe" ? "success" : "danger"}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TrafficChart data={trafficData} />
        <ThreatDistribution data={threatData} />
      </div>
    </div>
  );
}
