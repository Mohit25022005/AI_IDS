import { Shield, Activity, AlertTriangle, TrendingUp } from "lucide-react";
import MetricCard from "@/components/MetricCard";
import TrafficChart from "@/components/TrafficChart";
import ThreatDistribution from "@/components/ThreatDistribution";

export default function Dashboard() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Packets Analyzed"
          value="1.2M"
          icon={Activity}
          trend="+12.5%"
          variant="default"
        />
        <MetricCard
          title="Threats Detected"
          value="48"
          icon={AlertTriangle}
          trend="+8"
          variant="danger"
        />
        <MetricCard
          title="Model Accuracy"
          value="98.7%"
          icon={TrendingUp}
          trend="+0.3%"
          variant="success"
        />
        <MetricCard
          title="System Status"
          value="Safe"
          icon={Shield}
          variant="success"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TrafficChart />
        <ThreatDistribution />
      </div>
    </div>
  );
}
