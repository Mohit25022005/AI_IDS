import React, { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { api, predictIntrusion } from "@/lib/api.ts";

// ── Feature columns ──────────────────────────────────────────────
const LIVE_FEATURE_COLUMNS = [
  "duration","source_port","destination_port",
  "forward_packets","backward_packets",
  "forward_bytes","backward_bytes",
  "total_packets","total_bytes",
  "packets_per_second","bytes_per_second",
  "mean_packet_size","min_packet_size","max_packet_size","packet_size_std",
  "syn_count","ack_count","fin_count","rst_count","psh_count",
  "forward_packet_ratio","backward_packet_ratio",
  "forward_byte_ratio","backward_byte_ratio",
  "syn_ratio","rst_ratio","protocol",
];

// ── Pre-built test vectors — exact real samples from CIC-IDS-2017 test set
// These are actual rows that the Random Forest correctly classifies.
// source_port = 0 because CIC-IDS-2017 does not include source port.
const TEST_VECTORS: Record<string, Record<string, number | string>> = {
  normal: {
    duration: 115.544849, source_port: 0, destination_port: 80,
    forward_packets: 16, backward_packets: 14,
    forward_bytes: 437, backward_bytes: 796,
    total_packets: 30, total_bytes: 1233,
    packets_per_second: 0.259639441, bytes_per_second: 10.67118102,
    mean_packet_size: 39.77419355, min_packet_size: 0, max_packet_size: 796,
    packet_size_std: 160.7838528,
    syn_count: 0, ack_count: 0, fin_count: 0, rst_count: 0, psh_count: 1,
    forward_packet_ratio: 0.5333333333, backward_packet_ratio: 0.4666666667,
    forward_byte_ratio: 0.3544201135, backward_byte_ratio: 0.6455798865,
    syn_ratio: 0.0, rst_ratio: 0.0, protocol: "tcp",
  },
  probe: {
    // CIC PortScan: ultra-high pps, near-zero duration, tiny packets
    duration: 0.000018, source_port: 0, destination_port: 32778,
    forward_packets: 1, backward_packets: 1,
    forward_bytes: 0, backward_bytes: 6,
    total_packets: 2, total_bytes: 6,
    packets_per_second: 111111.1111, bytes_per_second: 333333.3333,
    mean_packet_size: 2.0, min_packet_size: 0, max_packet_size: 6,
    packet_size_std: 3.464101615,
    syn_count: 0, ack_count: 0, fin_count: 0, rst_count: 0, psh_count: 1,
    forward_packet_ratio: 0.5, backward_packet_ratio: 0.5,
    forward_byte_ratio: 0.0, backward_byte_ratio: 1.0,
    syn_ratio: 0.0, rst_ratio: 0.0, protocol: "tcp",
  },
  dos: {
    // CIC DoS Hulk: long duration, all-forward, zero bytes (connection exhaust)
    duration: 63.1404, source_port: 0, destination_port: 80,
    forward_packets: 7, backward_packets: 0,
    forward_bytes: 0, backward_bytes: 0,
    total_packets: 7, total_bytes: 0,
    packets_per_second: 0.110864043, bytes_per_second: 0.0,
    mean_packet_size: 0.0, min_packet_size: 0, max_packet_size: 0,
    packet_size_std: 0.0,
    syn_count: 0, ack_count: 0, fin_count: 0, rst_count: 0, psh_count: 1,
    forward_packet_ratio: 1.0, backward_packet_ratio: 0.0,
    forward_byte_ratio: 0.0, backward_byte_ratio: 0.0,
    syn_ratio: 0.0, rst_ratio: 0.0, protocol: "tcp",
  },
  ddos: {
    // CIC DDoS: large backward bytes, very high packet size std, asymmetric
    duration: 100.694233, source_port: 0, destination_port: 80,
    forward_packets: 8, backward_packets: 5,
    forward_bytes: 56, backward_bytes: 11607,
    total_packets: 13, total_bytes: 11663,
    packets_per_second: 0.129103719, bytes_per_second: 115.8258984,
    mean_packet_size: 833.5, min_packet_size: 0, max_packet_size: 5840,
    packet_size_std: 2103.115592,
    syn_count: 0, ack_count: 1, fin_count: 0, rst_count: 0, psh_count: 0,
    forward_packet_ratio: 0.6153846154, backward_packet_ratio: 0.3846153846,
    forward_byte_ratio: 0.004801509, backward_byte_ratio: 0.995198491,
    syn_ratio: 0.0, rst_ratio: 0.0, protocol: "tcp",
  },
  r2l: {
    // CIC SSH-Patator: brute-force SSH, backward-heavy, port 22
    duration: 12.767262, source_port: 0, destination_port: 22,
    forward_packets: 21, backward_packets: 32,
    forward_bytes: 2008, backward_bytes: 2745,
    total_packets: 53, total_bytes: 4753,
    packets_per_second: 4.151242451, bytes_per_second: 372.28029,
    mean_packet_size: 88.01851852, min_packet_size: 0, max_packet_size: 976,
    packet_size_std: 189.5902723,
    syn_count: 0, ack_count: 0, fin_count: 0, rst_count: 0, psh_count: 1,
    forward_packet_ratio: 0.3962264151, backward_packet_ratio: 0.6037735849,
    forward_byte_ratio: 0.4224700189, backward_byte_ratio: 0.5775299811,
    syn_ratio: 0.0, rst_ratio: 0.0, protocol: "tcp",
  },
  bot: {
    // CIC Bot: tiny packets, insanely high pps, C&C beaconing
    duration: 0.000003, source_port: 0, destination_port: 52238,
    forward_packets: 1, backward_packets: 1,
    forward_bytes: 6, backward_bytes: 6,
    total_packets: 2, total_bytes: 12,
    packets_per_second: 666666.6667, bytes_per_second: 4000000.0,
    mean_packet_size: 6.0, min_packet_size: 6, max_packet_size: 6,
    packet_size_std: 0.0,
    syn_count: 0, ack_count: 1, fin_count: 0, rst_count: 0, psh_count: 0,
    forward_packet_ratio: 0.5, backward_packet_ratio: 0.5,
    forward_byte_ratio: 0.5, backward_byte_ratio: 0.5,
    syn_ratio: 0.0, rst_ratio: 0.0, protocol: "tcp",
  },
  web_attack: {
    // CIC Web Attack Brute Force: slow rate, port 80, forward-heavy
    duration: 5.589674, source_port: 0, destination_port: 80,
    forward_packets: 3, backward_packets: 1,
    forward_bytes: 0, backward_bytes: 0,
    total_packets: 4, total_bytes: 0,
    packets_per_second: 0.715605239, bytes_per_second: 0.0,
    mean_packet_size: 0.0, min_packet_size: 0, max_packet_size: 0,
    packet_size_std: 0.0,
    syn_count: 0, ack_count: 0, fin_count: 0, rst_count: 0, psh_count: 1,
    forward_packet_ratio: 0.75, backward_packet_ratio: 0.25,
    forward_byte_ratio: 0.0, backward_byte_ratio: 0.0,
    syn_ratio: 0.0, rst_ratio: 0.0, protocol: "tcp",
  },
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-900/30 text-red-400 border-red-600/40",
  high:     "bg-orange-900/30 text-orange-400 border-orange-600/40",
  medium:   "bg-yellow-900/30 text-yellow-400 border-yellow-600/40",
  info:     "bg-blue-900/30 text-blue-400 border-blue-600/40",
};

const ATTACK_COLORS: Record<string, string> = {
  normal:     "text-green-500",
  probe:      "text-yellow-500",
  dos:        "text-red-500",
  ddos:       "text-red-600",
  r2l:        "text-orange-500",
  bot:        "text-purple-500",
  web_attack: "text-pink-500",
};

function predColor(pred: string) {
  return ATTACK_COLORS[pred?.toLowerCase()] ?? "text-red-500";
}

// ── Component ────────────────────────────────────────────────────
export default function Monitor() {
  const [features, setFeatures]             = useState<Record<string, number | string>>({});
  const [capturing, setCapturing]           = useState(false);
  const [captureMode, setCaptureMode]       = useState("normal");
  const [captureResults, setCaptureResults] = useState<any[]>([]);
  const [monitoring, setMonitoring]         = useState(false);
  const [result, setResult]                 = useState<any>(null);
  const [history, setHistory]               = useState<any[]>([]);
  const [alerts, setAlerts]                 = useState<any[]>([]);
  const { toast } = useToast();

  const updateFeature = (name: string, value: string) => {
    setFeatures(prev => ({ ...prev, [name]: value }));
  };

  // ── Data fetching ──────────────────────────────────────────────
  const fetchHistory = async () => {
    try {
      const res = await api.get("/monitor/history");
      setHistory(res.data.records || []);
    } catch { /* ignore */ }
  };

  const fetchAlerts = async () => {
    try {
      const res = await api.get("/alerts");
      setAlerts(res.data.alerts ?? []);   // FIX: unwrap paginated envelope
    } catch { /* ignore */ }
  };

  useEffect(() => {
    fetchHistory();
    fetchAlerts();
    const id = setInterval(() => { fetchHistory(); fetchAlerts(); }, 5000);
    return () => clearInterval(id);
  }, []);

  // ── Auto-predict trigger: set when a test vector is loaded ─────
  const [pendingPredict, setPendingPredict] = useState<Record<string, number | string> | null>(null);

  // ── Load a pre-built test vector ────────────────────────────────
  // Store the vector in pendingPredict — the useEffect below fires
  // after the state update and calls handlePredict with the fresh data.
  const loadTestVector = (cls: string) => {
    const vec = TEST_VECTORS[cls];
    if (!vec) return;
    setFeatures({ ...vec });
    setPendingPredict({ ...vec });
  };

  // When a test vector is loaded, run prediction immediately using
  // the freshly-stored vector (avoids stale-closure issue entirely).
  useEffect(() => {
    if (!pendingPredict) return;
    setPendingPredict(null);
    handlePredict(pendingPredict);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingPredict]);

  // ── Predict (accepts optional override to avoid stale-closure issues) ──
  const handlePredict = async (overrideFeatures?: Record<string, number | string>) => {
    const f = overrideFeatures ?? features;

    if (Object.keys(f).length !== LIVE_FEATURE_COLUMNS.length) {
      toast({ variant: "destructive", title: "Incomplete Features",
              description: `Load a test vector or fill all ${LIVE_FEATURE_COLUMNS.length} fields.` });
      return;
    }

    const prepared: Record<string, number | string> = {};
    for (const feat of LIVE_FEATURE_COLUMNS) {
      if (feat === "protocol") {
        const v = String(f[feat]).toLowerCase().trim();
        if (!["tcp","udp","other"].includes(v)) {
          toast({ variant: "destructive", title: "Invalid protocol",
                  description: "Must be tcp, udp, or other." });
          return;
        }
        prepared[feat] = v;
      } else {
        const v = Number(f[feat]);
        if (!Number.isFinite(v)) {
          toast({ variant: "destructive", title: "Invalid Feature",
                  description: `${feat} must be a number.` });
          return;
        }
        prepared[feat] = v;
      }
    }

    try {
      const res = await predictIntrusion(prepared);
      setResult(res);
      toast({
        title: "Prediction Complete",
        description: `${res.prediction.toUpperCase()}  ·  Confidence: ${(res.confidence * 100).toFixed(1)}%  ·  Anomaly: ${res.anomaly_score !== null ? (res.anomaly_score * 100).toFixed(0) + "%" : "N/A"}`,
      });
      fetchHistory();
      fetchAlerts();
    } catch (err: any) {
      toast({ variant: "destructive", title: "Prediction Error",
              description: err.response?.data?.error ?? err.message });
    }
  };

  // ── Capture ────────────────────────────────────────────────────
  const handleCapture = async () => {
    try {
      setCapturing(true);
      const response = await api.post("/capture", { capture_time: 5, mode: captureMode });
      const flows = response.data?.flows || [];
      setCaptureResults(flows);
      toast({ title: "Capture Complete",
              description: `${flows.length} flow(s) analysed.` });
      fetchHistory();
      fetchAlerts();
    } catch (err: any) {
      toast({ variant: "destructive", title: "Capture Failed",
              description: err.response?.data?.error ?? err.message });
    } finally {
      setCapturing(false);
    }
  };

  // ── Continuous monitoring ──────────────────────────────────────
  const monitoringRef = useRef(monitoring);
  monitoringRef.current = monitoring;

  useEffect(() => {
    if (!monitoring) return;
    const id = setInterval(() => { if (!capturing) handleCapture(); }, 10000);
    return () => clearInterval(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [monitoring]);

  // ── Simulate ───────────────────────────────────────────────────
  const handleSimulate = async (cls: string) => {
    try {
      const res = await api.post("/simulate", { class: cls, count: 5 });
      const results = res.data.results ?? [];
      const preds = results.map((r: any) => r.prediction).join(", ");
      toast({ title: `Simulate: ${cls.toUpperCase()}`,
              description: `5 synthetic flows → ${preds}` });
      fetchHistory();
      fetchAlerts();
    } catch (err: any) {
      toast({ variant: "destructive", title: "Simulate Failed",
              description: err.response?.data?.error ?? err.message });
    }
  };

  // ── Render ─────────────────────────────────────────────────────
  return (
    <div className="p-6 space-y-8">
      <h1 className="text-2xl font-semibold">Network Monitor</h1>

      {/* ── Quick Test Vectors ──────────────────────────────── */}
      <div className="rounded-lg border border-border p-4 space-y-3">
        <div>
          <h2 className="text-base font-semibold">Quick Test Vectors</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Load a pre-built feature vector based on real CIC-IDS-2017 samples,
            then click <strong>Predict</strong>.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {Object.keys(TEST_VECTORS).map(cls => (
            <Button
              key={cls}
              size="sm"
              variant="outline"
              className={`capitalize border ${
                cls === "normal"
                  ? "border-green-600/40 text-green-500 hover:bg-green-900/20"
                  : "border-red-600/40 text-red-400 hover:bg-red-900/20"
              }`}
              onClick={() => loadTestVector(cls)}
            >
              Load {cls.replace("_", " ")}
            </Button>
          ))}
        </div>
      </div>

      {/* ── Simulate Buttons ────────────────────────────────── */}
      <div className="rounded-lg border border-border p-4 space-y-3">
        <div>
          <h2 className="text-base font-semibold">Simulate Traffic</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Generate 5 synthetic flows per class and run them through the active model.
            Results appear in prediction history and may generate alerts.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {Object.keys(TEST_VECTORS).map(cls => (
            <Button
              key={cls}
              size="sm"
              variant="secondary"
              className="capitalize"
              onClick={() => handleSimulate(cls)}
            >
              Simulate {cls.replace("_", " ")}
            </Button>
          ))}
        </div>
      </div>

      {/* ── Prediction Result ────────────────────────────────── */}
      {result && (
        <div className={`rounded-lg border p-4 ${result.prediction?.toLowerCase() === "normal" ? "border-green-600/40 bg-green-900/10" : "border-red-600/40 bg-red-900/10"}`}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Last Prediction</p>
              <p className={`text-2xl font-bold ${predColor(result.prediction)}`}>
                {result.prediction?.toUpperCase()}
              </p>
            </div>
            <div className="grid grid-cols-3 gap-4 text-right">
              <div>
                <p className="text-xs text-muted-foreground">Confidence</p>
                <p className="text-lg font-semibold">{(result.confidence * 100).toFixed(1)}%</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Anomaly Score</p>
                <p className={`text-lg font-semibold ${(result.anomaly_score ?? 0) > 0.60 ? "text-red-400" : "text-green-400"}`}>
                  {result.anomaly_score !== null ? (result.anomaly_score * 100).toFixed(0) + "%" : "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Latency</p>
                <p className="text-lg font-semibold">{result.latency_ms?.toFixed(3)} ms</p>
              </div>
            </div>
          </div>
          {/* SHAP top-5 */}
          {result.shap_top5?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-border/50">
              <p className="text-xs text-muted-foreground mb-2">Top SHAP contributions</p>
              <div className="space-y-1">
                {result.shap_top5.map((s: any) => {
                  const pos = s.contribution >= 0;
                  const max = Math.max(...result.shap_top5.map((x: any) => Math.abs(x.contribution)));
                  const pct = Math.round(Math.abs(s.contribution) / max * 100);
                  return (
                    <div key={s.feature} className="flex items-center gap-2 text-xs">
                      <span className="w-28 font-mono text-muted-foreground truncate">{s.feature}</span>
                      <div className="flex-1 h-1.5 rounded bg-muted overflow-hidden">
                        <div className={`h-full rounded ${pos ? "bg-red-500" : "bg-blue-500"}`} style={{ width: `${pct}%` }} />
                      </div>
                      <span className={`w-16 text-right ${pos ? "text-red-400" : "text-blue-400"}`}>
                        {s.contribution > 0 ? "+" : ""}{s.contribution.toFixed(4)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Manual Feature Entry + Actions ──────────────────── */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold">Manual Feature Entry</h2>
          <div className="flex gap-2">
            <Button size="sm" onClick={handlePredict}>
              Predict
            </Button>
            <div className="flex items-center gap-2">
              <select
                value={captureMode}
                onChange={e => setCaptureMode(e.target.value)}
                disabled={capturing || monitoring}
                className="text-xs px-2 py-1.5 rounded border border-border bg-background text-foreground"
              >
                <option value="normal">Normal capture</option>
                <option value="probe">Probe capture</option>
              </select>
              <Button size="sm" variant="outline" onClick={handleCapture} disabled={capturing || monitoring}>
                {capturing ? "Capturing…" : "Capture & Detect"}
              </Button>
              <Button size="sm" variant={monitoring ? "destructive" : "outline"}
                onClick={() => setMonitoring(m => !m)} disabled={capturing}>
                {monitoring ? "Stop Monitor" : "Start Monitor"}
              </Button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {LIVE_FEATURE_COLUMNS.map(feat => (
            <div key={feat} className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">{feat}</label>
              <Input
                type={feat === "protocol" ? "text" : "number"}
                step={feat === "protocol" ? undefined : "any"}
                value={features[feat] ?? ""}
                onChange={e => updateFeature(feat, e.target.value)}
                placeholder={feat === "protocol" ? "tcp/udp/other" : "0"}
                className="h-8 text-xs"
              />
            </div>
          ))}
        </div>
      </div>

      {/* ── Capture Results ─────────────────────────────────── */}
      {captureResults.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-base font-semibold">Captured Flows</h2>
          {captureResults.map((flow, i) => (
            <div key={i} className="rounded-lg border border-border p-3 flex justify-between items-start">
              <div className="text-xs text-muted-foreground space-y-0.5">
                <p>{flow.timestamp}</p>
                <p>Port {flow.features?.destination_port} · {flow.features?.protocol?.toUpperCase()}</p>
                <p>{flow.features?.total_packets} pkts · {flow.features?.total_bytes} bytes</p>
              </div>
              <div className="text-right">
                <p className={`font-bold text-sm ${predColor(flow.prediction)}`}>
                  {flow.prediction?.toUpperCase()}
                </p>
                <p className="text-xs text-muted-foreground">{(flow.confidence * 100).toFixed(1)}%</p>
                {flow.anomaly_score !== null && (
                  <p className={`text-xs ${flow.anomaly_score > 0.60 ? "text-red-400" : "text-muted-foreground"}`}>
                    anomaly: {(flow.anomaly_score * 100).toFixed(0)}%
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Prediction History ───────────────────────────────── */}
      <div className="space-y-2">
        <h2 className="text-base font-semibold">Prediction History</h2>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/20">
                {["Timestamp","Source","Destination","Protocol","Prediction","Confidence","Anomaly"].map(h => (
                  <th key={h} className="text-left py-2 px-3 text-xs font-medium text-muted-foreground">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {history.length === 0 && (
                <tr><td colSpan={7} className="py-6 text-center text-sm text-muted-foreground">No predictions yet</td></tr>
              )}
              {history.map((item, idx) => (
                <tr key={idx} className="border-b border-border/40 hover:bg-secondary/20 transition-colors">
                  <td className="py-2 px-3 text-xs">{item.timestamp}</td>
                  <td className="py-2 px-3 text-xs font-mono">
                    {item.sourceIP || "N/A"}{item.sourcePort ? `:${item.sourcePort}` : ""}
                  </td>
                  <td className="py-2 px-3 text-xs font-mono">
                    {item.destinationIP || "N/A"}{item.destinationPort ? `:${item.destinationPort}` : ""}
                  </td>
                  <td className="py-2 px-3 text-xs uppercase">{item.protocol || "N/A"}</td>
                  <td className={`py-2 px-3 text-xs font-bold ${predColor(item.prediction)}`}>
                    {item.prediction?.toUpperCase() || "?"}
                  </td>
                  <td className="py-2 px-3 text-xs">{typeof item.confidence === "number" ? `${item.confidence}%` : "N/A"}</td>
                  <td className="py-2 px-3 text-xs">
                    {item.anomaly_score !== null && item.anomaly_score !== undefined
                      ? <span className={item.anomaly_score > 0.60 ? "text-red-400 font-semibold" : "text-muted-foreground"}>
                          {(item.anomaly_score * 100).toFixed(0)}%
                        </span>
                      : <span className="text-muted-foreground">—</span>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Active Alerts ────────────────────────────────────── */}
      <div className="space-y-2">
        <h2 className="text-base font-semibold">
          Active Alerts{alerts.length > 0 && <span className="ml-2 text-xs text-red-400">({alerts.length})</span>}
        </h2>
        {alerts.length === 0
          ? <p className="text-sm text-muted-foreground py-3">No active alerts</p>
          : <div className="space-y-2">
              {alerts.map(alert => (
                <div key={alert.id} className={`rounded-lg border p-3 ${SEVERITY_COLORS[alert.severity] ?? SEVERITY_COLORS.medium}`}>
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-sm">{alert.type}</p>
                    <Badge className={SEVERITY_COLORS[alert.severity] ?? ""}>
                      {alert.severity?.toUpperCase()}
                    </Badge>
                  </div>
                  <p className="text-xs mt-1 opacity-80">{alert.description}</p>
                  <p className="text-xs mt-0.5 opacity-60">{alert.timestamp}</p>
                </div>
              ))}
            </div>
        }
      </div>
    </div>
  );
}
