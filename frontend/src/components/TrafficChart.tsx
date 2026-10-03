import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from "recharts";
import { api } from "@/lib/api";

interface DataPoint {
  time: string;
  normal: number;
  attack: number;
}

/** Keep a rolling window of per-poll snapshots to draw a time series. */
const MAX_POINTS = 20;

export default function TrafficChart() {
  const [series, setSeries] = useState<DataPoint[]>([]);
  const [prevNormal, setPrevNormal] = useState(0);
  const [prevAttack, setPrevAttack] = useState(0);

  useEffect(() => {
    const tick = async () => {
      try {
        const res = await api.get("/monitor/history?limit=1&page=1");
        const data = res.data;
        const normalNow: number = data.normal_count ?? 0;
        const attackNow: number = data.attack_count ?? 0;

        const newNormal = Math.max(0, normalNow - prevNormal);
        const newAttack = Math.max(0, attackNow - prevAttack);
        setPrevNormal(normalNow);
        setPrevAttack(attackNow);

        const ts = new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });

        setSeries((prev) => {
          const next = [...prev, { time: ts, normal: newNormal, attack: newAttack }];
          return next.length > MAX_POINTS ? next.slice(next.length - MAX_POINTS) : next;
        });
      } catch {
        // backend not reachable — skip tick
      }
    };

    tick();
    const id = setInterval(tick, 5000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prevNormal, prevAttack]);

  return (
    <Card className="border-border bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="text-foreground">Network Traffic</CardTitle>
        <p className="text-sm text-muted-foreground">
          New events per 5-second poll
        </p>
      </CardHeader>
      <CardContent>
        {series.length === 0 ? (
          <div className="flex items-center justify-center h-[300px] text-muted-foreground text-sm">
            Waiting for traffic data…
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={series}>
              <defs>
                <linearGradient id="colorNormal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="hsl(var(--chart-1))" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="hsl(var(--chart-1))" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorAttack" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="hsl(var(--destructive))" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="hsl(var(--destructive))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
              <XAxis dataKey="time" stroke="hsl(var(--muted-foreground))" fontSize={11} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} allowDecimals={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "0.5rem",
                }}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="normal"
                name="Normal"
                stroke="hsl(var(--chart-1))"
                fillOpacity={1}
                fill="url(#colorNormal)"
                strokeWidth={2}
              />
              <Area
                type="monotone"
                dataKey="attack"
                name="Attack"
                stroke="hsl(var(--destructive))"
                fillOpacity={1}
                fill="url(#colorAttack)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
