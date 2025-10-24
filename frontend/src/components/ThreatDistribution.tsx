import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

const mockData = [
  { name: "DDoS", value: 45, color: "hsl(var(--chart-5))" },
  { name: "Malware", value: 30, color: "hsl(var(--chart-4))" },
  { name: "Phishing", value: 15, color: "hsl(var(--chart-2))" },
  { name: "SQL Injection", value: 10, color: "hsl(var(--chart-3))" },
];

export default function ThreatDistribution() {
  return (
    <Card className="border-border bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="text-foreground">Threat Distribution</CardTitle>
        <p className="text-sm text-muted-foreground">Attack types detected today</p>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-6">
          <ResponsiveContainer width="50%" height={200}>
            <PieChart>
              <Pie
                data={mockData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={5}
                dataKey="value"
              >
                {mockData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "0.5rem",
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex-1 space-y-3">
            {mockData.map((item, index) => (
              <div key={index} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-sm text-foreground">{item.name}</span>
                </div>
                <span className="text-sm font-medium text-muted-foreground">{item.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
