import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { api } from "@/lib/api";

interface Slice {
  name: string;
  value: number;
  color: string;
}

const COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--destructive))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
];

const EMPTY: Slice[] = [{ name: "No data yet", value: 1, color: "hsl(var(--muted))" }];

export default function ThreatDistribution() {
  const [slices, setSlices] = useState<Slice[]>(EMPTY);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.get("/insights/traffic");
        const items: { name: string; count: number }[] = res.data ?? [];
        const filtered = items.filter((i) => i.count > 0);
        if (filtered.length === 0) {
          setSlices(EMPTY);
          setTotal(0);
          return;
        }
        const tot = filtered.reduce((s, i) => s + i.count, 0);
        setTotal(tot);
        setSlices(
          filtered.map((item, idx) => ({
            name: item.name,
            value: item.count,
            color: COLORS[idx % COLORS.length],
          }))
        );
      } catch {
        // backend not reachable
      }
    };

    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <Card className="border-border bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="text-foreground">Traffic Distribution</CardTitle>
        <p className="text-sm text-muted-foreground">
          Detected event classes (live predictions)
        </p>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-6">
          <ResponsiveContainer width="50%" height={200}>
            <PieChart>
              <Pie
                data={slices}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={5}
                dataKey="value"
              >
                {slices.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "0.5rem",
                }}
                formatter={(value: number, name: string) => [
                  `${value} (${total > 0 ? ((value / total) * 100).toFixed(1) : 0}%)`,
                  name,
                ]}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex-1 space-y-3">
            {slices.map((item, index) => (
              <div key={index} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                  <span className="text-sm text-foreground">{item.name}</span>
                </div>
                <span className="text-sm font-medium text-muted-foreground">
                  {total > 0 ? `${((item.value / total) * 100).toFixed(1)}%` : "—"}
                </span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
