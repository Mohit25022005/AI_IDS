import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// ✅ Define props type
type TrafficData = {
  name: string;   // "Normal" | "Attack"
  count: number;
};

type TrafficChartProps = {
  data: TrafficData[];
};

export default function TrafficChart({ data }: TrafficChartProps) {

  // 🔥 Transform backend data → chart format
  const chartData = data.map((item, index) => ({
    time: `T${index}`,
    incoming: item.count,
    outgoing: item.count * 0.7, // simulated outgoing
  }));

  return (
    <Card className="border-border bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="text-foreground">Network Traffic</CardTitle>
        <p className="text-sm text-muted-foreground">
          Real-time packet flow
        </p>
      </CardHeader>

      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={chartData}>

            <defs>
              <linearGradient id="colorIncoming" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(var(--chart-1))" stopOpacity={0.3} />
                <stop offset="95%" stopColor="hsl(var(--chart-1))" stopOpacity={0} />
              </linearGradient>

              <linearGradient id="colorOutgoing" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(var(--chart-2))" stopOpacity={0.3} />
                <stop offset="95%" stopColor="hsl(var(--chart-2))" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />

            <XAxis dataKey="time" fontSize={12} />
            <YAxis fontSize={12} />

            <Tooltip />

            <Area
              type="monotone"
              dataKey="incoming"
              stroke="hsl(var(--chart-1))"
              fillOpacity={1}
              fill="url(#colorIncoming)"
              strokeWidth={2}
            />

            <Area
              type="monotone"
              dataKey="outgoing"
              stroke="hsl(var(--chart-2))"
              fillOpacity={1}
              fill="url(#colorOutgoing)"
              strokeWidth={2}
            />

          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}