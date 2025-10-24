import { useEffect, useState } from "react";
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
  });

  const [trafficData, setTrafficData] = useState([]);
  const [threatData, setThreatData] = useState([]);

  useEffect(() => {
    // Fetch overall metrics
    api.get("/dashboard/metrics")
      .then(res => setMetrics(res.data))
      .catch(console.error);

    // Fetch traffic data for chart
    api.get("/dashboard/traffic")
      .then(res => setTrafficData(res.data))
      .catch(console.error);

    // Fetch threat distribution data
    api.get("/dashboard/threats")
      .then(res => setThreatData(res.data))
      .catch(console.error);
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
