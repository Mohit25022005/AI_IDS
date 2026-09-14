import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
import { api, predictIntrusion } from "@/lib/api";

export default function Monitor() {
  const [features, setFeatures] = useState({});
  const [capturing, setCapturing] = useState(false);
  const [captureResults, setCaptureResults] = useState([]);
  const [monitoring, setMonitoring] = useState(false);
  const [result, setResult] = useState(null);
  const LIVE_FEATURE_COLUMNS = [
    "duration",
    "source_port",
    "destination_port",
    "forward_packets",
    "backward_packets",
    "forward_bytes",
    "backward_bytes",
    "total_packets",
    "total_bytes",
    "packets_per_second",
    "bytes_per_second",
    "mean_packet_size",
    "min_packet_size",
    "max_packet_size",
    "packet_size_std",
    "syn_count",
    "ack_count",
    "fin_count",
    "rst_count",
    "psh_count",
    "forward_packet_ratio",
    "backward_packet_ratio",
    "forward_byte_ratio",
    "backward_byte_ratio",
    "syn_ratio",
    "rst_ratio",
    "protocol",
  ];
  const updateFeature = (name, value) => {
    setFeatures((previous) => ({
      ...previous,
      [name]: value,
    }));
  };
  const [history, setHistory] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const { toast } = useToast();

  // Fetch prediction history
  const fetchHistory = async () => {
    try {
      const res = await api.get("/monitor/history");
      setHistory(res.data);
    } catch (err) {
      console.error("Error fetching history:", err);
    }
  };

  // Fetch alerts
  const fetchAlerts = async () => {
    try {
      const res = await api.get("/alerts");
      setAlerts(res.data);
    } catch (err) {
      console.error("Error fetching alerts:", err);
    }
  };

  useEffect(() => {
    fetchHistory();
    fetchAlerts();
    const interval = setInterval(() => {
      fetchHistory();
      fetchAlerts();
    }, 5000); // update every 5s
    return () => clearInterval(interval);
  }, []);
  const loadProbeTest = () => {
    setFeatures({
      duration: 0.15,
      source_port: 50000,
      destination_port: 8000,
      forward_packets: 1,
      backward_packets: 1,
      forward_bytes: 50,
      backward_bytes: 50,
      total_packets: 2,
      total_bytes: 100,
      packets_per_second: 13.33,
      bytes_per_second: 666.67,
      mean_packet_size: 50,
      min_packet_size: 50,
      max_packet_size: 50,
      packet_size_std: 0,
      syn_count: 1,
      ack_count: 0,
      fin_count: 0,
      rst_count: 1,
      psh_count: 0,
      forward_packet_ratio: 0.5,
      backward_packet_ratio: 0.5,
      forward_byte_ratio: 0.5,
      backward_byte_ratio: 0.5,
      syn_ratio: 0.5,
      rst_ratio: 0.5,
      protocol: "tcp",
    });
  };
  const handleCapture = async () => {
    try {
      setCapturing(true);

      const response = await api.post("/capture", {
        capture_time: 5,
      });

      const flows = response.data?.flows || [];

      setCaptureResults(flows);

      toast({
        title: "Capture Completed",
        description: `${flows.length} network flow(s) captured and analyzed.`,
      });

      fetchHistory();
      fetchAlerts();

    } catch (err) {
      console.error("Capture error:", err);

      const errorMsg =
        err.response?.data?.error ||
        err.message ||
        "Unable to capture network traffic.";

      toast({
        variant: "destructive",
        title: "Capture Failed",
        description: errorMsg,
      });

    } finally {
      setCapturing(false);
    }
  };
  const handleStartMonitoring = () => {
    setMonitoring(true);
  };

  const handleStopMonitoring = () => {
    setMonitoring(false);
  };
  useEffect(() => {
    if (!monitoring) {
      return;
    }

    const runCapture = async () => {
      if (capturing) {
        return;
      }

      await handleCapture();
    };

    runCapture();

    const interval = setInterval(() => {
      runCapture();
    }, 10000);

    return () => clearInterval(interval);
  }, [monitoring]);

  const handlePredict = async () => {
    try {
      if (Object.keys(features).length !== LIVE_FEATURE_COLUMNS.length) {
        toast({
          variant: "destructive",
          title: "Incomplete Features",
          description: `Please provide all ${LIVE_FEATURE_COLUMNS.length} live-flow features.`,
        });
        return;
      }

      const preparedFeatures = {};

      for (const feature of LIVE_FEATURE_COLUMNS) {
        if (feature === "protocol") {
          preparedFeatures[feature] = String(features[feature]).toLowerCase();
          continue;
        }

        const value = Number(features[feature]);

        if (!Number.isFinite(value)) {
          toast({
            variant: "destructive",
            title: "Invalid Feature",
            description: `${feature} must be a valid number.`,
          });
          return;
        }

        preparedFeatures[feature] = value;
      }

      const res = await predictIntrusion(preparedFeatures);

      setResult(res.prediction);

      toast({
        title: "Prediction Successful",
        description: `Result: ${res.prediction.toUpperCase()} (Confidence: ${(res.confidence * 100).toFixed(1)}%)`,
      });

      fetchHistory();
      fetchAlerts();

    } catch (err) {
      console.error(err);

      const errorMsg =
        err.response?.data?.error ||
        err.message ||
        "Unable to connect to the backend API.";

      toast({
        variant: "destructive",
        title: "Prediction Error",
        description: errorMsg,
      });
    }
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-semibold">Network Monitor</h1>

      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">
            Live Network Flow Features
          </h2>

          <p className="text-sm text-muted-foreground">
            Enter the 27 features extracted from a captured network flow.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {LIVE_FEATURE_COLUMNS.map((feature) => (
            <div key={feature} className="space-y-2">
              <label className="text-sm font-medium">
                {feature}
              </label>

              <Input
                type={feature === "protocol" ? "text" : "number"}
                step={feature === "protocol" ? undefined : "any"}
                value={features[feature] ?? ""}
                onChange={(e) =>
                  updateFeature(feature, e.target.value)
                }
                placeholder={
                  feature === "protocol"
                    ? "tcp / udp / other"
                    : `Enter ${feature}`
                }
              />
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap gap-3 mt-4">
        <Button onClick={handlePredict}>
          Predict Manual Features
        </Button>

        <Button
          type="button"
          variant="outline"
          onClick={loadProbeTest}
        >
          Load Probe Test
        </Button>

        <Button
          type="button"
          onClick={handleCapture}
          disabled={capturing || monitoring}
        >
          {capturing ? "Capturing..." : "Capture & Detect"}
        </Button>

        <Button
          type="button"
          variant="outline"
          onClick={monitoring ? handleStopMonitoring : handleStartMonitoring}
          disabled={capturing}
        >
          {monitoring ? "Stop Monitoring" : "Start Monitoring"}
        </Button>
      </div>

      {result && (
        <div className="p-4 border rounded-lg mt-4">
          <h2 className="font-bold text-lg">
            🧠 Prediction:{" "}
            <span
              className={
                result?.toLowerCase() === "normal"
                  ? "text-green-600"
                  : "text-red-600"
              }
            >
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
                <td
                  className={`py-3 px-4 text-sm font-bold ${item.prediction?.toLowerCase() === "normal"
                    ? "text-green-600"
                    : "text-red-600"
                    }`}
                >
                  {item.prediction.toUpperCase()}
                </td>
                <td className="py-3 px-4 text-sm text-foreground">{(item.confidence * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Alerts */}
      <div className="mt-6">
        <h2 className="text-xl font-semibold">Alerts</h2>
        <ul className="space-y-2 mt-2">
          {alerts.length ? alerts.map((alert) => (
            <li key={alert.id} className="p-3 border rounded-lg bg-black-50 border-red-200">
              <p className="font-bold">{alert.type}</p>
              <p>{alert.description}</p>
              <p className="text-sm text-muted-foreground">{alert.timestamp}</p>
            </li>
          )) : <p className="text-sm text-muted-foreground">No active alerts</p>}
        </ul>
      </div>
      {captureResults.length > 0 && (
        <div className="mt-6 space-y-4">
          <div>
            <h2 className="text-lg font-semibold">
              Latest Captured Flows
            </h2>

            <p className="text-sm text-muted-foreground">
              Results from the most recent 5-second network capture.
            </p>
          </div>

          <div className="space-y-3">
            {captureResults.map((flow, index) => (
              <div
                key={`${flow.timestamp}-${index}`}
                className="rounded-lg border p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-medium">
                      Flow {index + 1}
                    </p>

                    <p className="text-sm text-muted-foreground">
                      {flow.timestamp}
                    </p>
                  </div>

                  <div className="text-right">
                    <p
                      className={
                        flow.prediction?.toLowerCase() === "normal"
                          ? "font-semibold text-green-600"
                          : "font-semibold text-red-600"
                      }
                    >
                      {flow.prediction?.toUpperCase()}
                    </p>

                    <p className="text-sm text-muted-foreground">
                      Confidence:{" "}
                      {(flow.confidence * 100).toFixed(1)}%
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>

  );
}
