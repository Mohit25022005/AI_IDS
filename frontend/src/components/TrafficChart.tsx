import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const mockData = [
  { time: "00:00", incoming: 120, outgoing: 95 },
  { time: "00:05", incoming: 180, outgoing: 130 },
  { time: "00:10", incoming: 150, outgoing: 110 },
  { time: "00:15", incoming: 220, outgoing: 160 },
  { time: "00:20", incoming: 195, outgoing: 145 },
  { time: "00:25", incoming: 240, outgoing: 180 },
  { time: "00:30", incoming: 210, outgoing: 155 },
  { time: "00:35", incoming: 270, outgoing: 200 },
];

export default function TrafficChart() {
  return (
    <Card className="border-border bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="text-foreground">Network Traffic</CardTitle>
        <p className="text-sm text-muted-foreground">Real-time packet flow per second</p>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={mockData}>
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
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
            <XAxis
              dataKey="time"
              stroke="hsl(var(--muted-foreground))"
              fontSize={12}
            />
            <YAxis
              stroke="hsl(var(--muted-foreground))"
              fontSize={12}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "0.5rem",
              }}
            />
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
