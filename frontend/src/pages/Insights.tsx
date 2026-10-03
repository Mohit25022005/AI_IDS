import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */
interface ModelMetrics {
  model: string;
  accuracy: number;
  precision_macro: number;
  recall_macro: number;
  f1_macro: number;
  f1_weighted: number;
  roc_auc: number | null;
  pr_auc: number | null;
  n_test_samples: number | null;
  evaluation_type: string;
}

interface PerClassRow {
  precision: number;
  recall: number;
  f1: number;
  support: number;
}

interface ComparisonRow {
  model: string;
  accuracy: number;
  precision_macro: number;
  recall_macro: number;
  f1_macro: number;
  latency_ms_per_sample: number;
}

interface LatencyPoint {
  idx: number;
  latency_ms: number;
}

const EMPTY_METRICS: ModelMetrics = {
  model: "—",
  accuracy: 0,
  precision_macro: 0,
  recall_macro: 0,
  f1_macro: 0,
  f1_weighted: 0,
  roc_auc: null,
  pr_auc: null,
  n_test_samples: null,
  evaluation_type: "—",
};

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */
const pct = (v: number | null | undefined) =>
  v != null ? `${v.toFixed(2)}%` : "—";

const fmt4 = (v: number | null | undefined) =>
  v != null ? v.toFixed(4) : "—";

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */
export default function Insights() {
  const [metrics, setMetrics] = useState<ModelMetrics>(EMPTY_METRICS);
  const [confusionMatrix, setConfusionMatrix] = useState<number[][]>([]);
  const [confusionLabels, setConfusionLabels] = useState<string[]>([]);
  const [trafficData, setTrafficData] = useState<{ name: string; count: number }[]>([]);
  const [perClass, setPerClass] = useState<Record<string, PerClassRow>>({});
  const [perClassLabels, setPerClassLabels] = useState<string[]>([]);
  const [comparison, setComparison] = useState<ComparisonRow[]>([]);
  const [latencySamples, setLatencySamples] = useState<LatencyPoint[]>([]);
  const [latencyStats, setLatencyStats] = useState<{
    avg_ms: number | null;
    p50_ms: number | null;
    p95_ms: number | null;
    p99_ms: number | null;
  }>({ avg_ms: null, p50_ms: null, p95_ms: null, p99_ms: null });

  const loadAll = async () => {
    try {
      const [mRes, cRes, tRes, pcRes, compRes, latRes] = await Promise.all([
        api.get("/insights/metrics"),
        api.get("/insights/confusion"),
        api.get("/insights/traffic"),
        api.get("/insights/metrics/perclass"),
        api.get("/model/comparison"),
        api.get("/insights/latency?n=50"),
      ]);

      setMetrics(mRes.data ?? EMPTY_METRICS);

      setConfusionMatrix(cRes.data?.matrix ?? []);
      setConfusionLabels(cRes.data?.labels ?? []);

      setTrafficData(tRes.data ?? []);

      setPerClass(pcRes.data?.per_class ?? {});
      setPerClassLabels(pcRes.data?.classes ?? []);

      setComparison(compRes.data ?? []);

      const samples: number[] = latRes.data?.samples ?? [];
      setLatencySamples(samples.map((v, i) => ({ idx: i + 1, latency_ms: v })));
      setLatencyStats({
        avg_ms: latRes.data?.avg_ms ?? null,
        p50_ms: latRes.data?.p50_ms ?? null,
        p95_ms: latRes.data?.p95_ms ?? null,
        p99_ms: latRes.data?.p99_ms ?? null,
      });
    } catch {
      // backend not reachable
    }
  };

  useEffect(() => {
    loadAll();
    const id = setInterval(loadAll, 5000);
    return () => clearInterval(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* -- render -------------------------------------------------------- */
  return (
    <div className="space-y-6">

      {/* ── Active model performance ─────────────────────────────── */}
      <Card className="border-border bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-foreground">Model Performance</CardTitle>
          <p className="text-sm text-muted-foreground">
            Independent test-set evaluation · active model:{" "}
            <span className="font-medium text-foreground">{metrics.model}</span>
            {metrics.n_test_samples != null && ` · ${metrics.n_test_samples} samples`}
          </p>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
            {[
              { label: "Accuracy",   value: pct(metrics.accuracy) },
              { label: "Precision",  value: pct(metrics.precision_macro) },
              { label: "Recall",     value: pct(metrics.recall_macro) },
              { label: "F1 Macro",   value: pct(metrics.f1_macro) },
              { label: "F1 Weighted",value: pct(metrics.f1_weighted) },
              { label: "ROC-AUC",    value: fmt4(metrics.roc_auc) },
              { label: "PR-AUC",     value: fmt4(metrics.pr_auc) },
            ].map(({ label, value }) => (
              <div key={label} className="p-4 rounded-lg bg-gradient-cyber border border-primary/30">
                <p className="text-xs text-muted-foreground mb-1">{label}</p>
                <p className="text-xl font-bold text-foreground">{value}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* ── Per-class metrics ────────────────────────────────────── */}
      {perClassLabels.length > 0 && (
        <Card className="border-border bg-card/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-foreground">Per-Class Metrics</CardTitle>
            <p className="text-sm text-muted-foreground">Independent test set</p>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    {["Class", "Precision", "Recall", "F1", "Support"].map((h) => (
                      <th key={h} className="text-left py-2 px-3 text-muted-foreground font-medium">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {perClassLabels.map((cls) => {
                    const row = perClass[cls];
                    if (!row) return null;
                    return (
                      <tr key={cls} className="border-b border-border/40 hover:bg-secondary/20">
                        <td className="py-2 px-3 font-medium capitalize">{cls}</td>
                        <td className="py-2 px-3">{(row.precision * 100).toFixed(2)}%</td>
                        <td className="py-2 px-3">{(row.recall    * 100).toFixed(2)}%</td>
                        <td className="py-2 px-3">{(row.f1        * 100).toFixed(2)}%</td>
                        <td className="py-2 px-3">{row.support}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Confusion matrix ─────────────────────────────────────── */}
      {confusionMatrix.length > 0 && (
        <Card className="border-border bg-card/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-foreground">Confusion Matrix</CardTitle>
            <p className="text-sm text-muted-foreground">Independent test set</p>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              {/* Column headers */}
              <div className="inline-grid" style={{ gridTemplateColumns: `auto repeat(${confusionLabels.length}, 1fr)` }}>
                <div className="p-3" />
                {confusionLabels.map((lbl) => (
                  <div key={lbl} className="p-3 text-center text-sm font-medium text-muted-foreground capitalize">
                    Predicted {lbl}
                  </div>
                ))}
                {confusionMatrix.map((row, ri) => (
                  <>
                    <div key={`row-${ri}`} className="p-3 flex items-center text-sm font-medium text-muted-foreground capitalize">
                      Actual {confusionLabels[ri] ?? ri}
                    </div>
                    {row.map((cell, ci) => (
                      <div
                        key={`cell-${ri}-${ci}`}
                        className={`p-6 text-center rounded-lg m-1 ${
                          ri === ci
                            ? "bg-success/20 border border-success/30"
                            : "bg-destructive/20 border border-destructive/30"
                        }`}
                      >
                        <span className="text-2xl font-bold text-foreground">{cell}</span>
                      </div>
                    ))}
                  </>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Model comparison ─────────────────────────────────────── */}
      {comparison.length > 0 && (
        <Card className="border-border bg-card/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-foreground">Model Comparison</CardTitle>
            <p className="text-sm text-muted-foreground">
              All trained models · independent test set
            </p>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto mb-6">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    {["Model", "Accuracy", "Precision", "Recall", "F1 Macro", "Latency (ms)"].map((h) => (
                      <th key={h} className="text-left py-2 px-3 text-muted-foreground font-medium">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {comparison.map((row) => (
                    <tr key={row.model} className="border-b border-border/40 hover:bg-secondary/20">
                      <td className="py-2 px-3 font-medium capitalize">{row.model.replace(/_/g, " ")}</td>
                      <td className="py-2 px-3">{(row.accuracy          * 100).toFixed(2)}%</td>
                      <td className="py-2 px-3">{(row.precision_macro   * 100).toFixed(2)}%</td>
                      <td className="py-2 px-3">{(row.recall_macro      * 100).toFixed(2)}%</td>
                      <td className="py-2 px-3">{(row.f1_macro          * 100).toFixed(2)}%</td>
                      <td className="py-2 px-3">{row.latency_ms_per_sample.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={comparison.map((r) => ({
                name: r.model.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
                "F1 Macro": parseFloat((r.f1_macro * 100).toFixed(2)),
                "Accuracy": parseFloat((r.accuracy * 100).toFixed(2)),
              }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
                <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" fontSize={11} />
                <YAxis domain={[0, 100]} stroke="hsl(var(--muted-foreground))" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "0.5rem",
                  }}
                />
                <Legend />
                <Bar dataKey="Accuracy"  fill="hsl(var(--chart-1))" radius={[4,4,0,0]} />
                <Bar dataKey="F1 Macro"  fill="hsl(var(--chart-3))" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* ── Detection latency ────────────────────────────────────── */}
      <Card className="border-border bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-foreground">Detection Latency</CardTitle>
          <p className="text-sm text-muted-foreground">
            Last 50 inference calls (ms)
          </p>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            {[
              { label: "Avg",  value: latencyStats.avg_ms },
              { label: "p50",  value: latencyStats.p50_ms },
              { label: "p95",  value: latencyStats.p95_ms },
              { label: "p99",  value: latencyStats.p99_ms },
            ].map(({ label, value }) => (
              <div key={label} className="p-3 rounded-lg border border-border bg-secondary/10">
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="text-lg font-bold">
                  {value != null ? `${value.toFixed(3)} ms` : "—"}
                </p>
              </div>
            ))}
          </div>
          {latencySamples.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={latencySamples}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
                <XAxis dataKey="idx" stroke="hsl(var(--muted-foreground))" fontSize={11} label={{ value: "Sample #", position: "insideBottom", offset: -4 }} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} label={{ value: "ms", angle: -90, position: "insideLeft" }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "0.5rem",
                  }}
                  formatter={(v: number) => [`${v.toFixed(4)} ms`, "Latency"]}
                />
                <Line type="monotone" dataKey="latency_ms" stroke="hsl(var(--chart-2))" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-8">
              No latency data yet — make some predictions first.
            </p>
          )}
        </CardContent>
      </Card>

      {/* ── Live traffic distribution ────────────────────────────── */}
      <Card className="border-border bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-foreground">Live Traffic Counts</CardTitle>
          <p className="text-sm text-muted-foreground">
            All predictions since last backend restart
          </p>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={trafficData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
              <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" fontSize={12} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} allowDecimals={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "0.5rem",
                }}
              />
              <Bar dataKey="count" fill="hsl(var(--chart-1))" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

    </div>
  );
}
