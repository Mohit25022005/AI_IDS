import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

// ✅ Define alert type
type Alert = {
  id: number;
  type: string;
  description: string;
  timestamp: string;
};

// ✅ Props
type ThreatDistributionProps = {
  data: Alert[];
};

export default function ThreatDistribution({ data }: ThreatDistributionProps) {

  // 🔥 Convert alerts → grouped counts
  const grouped = data.reduce((acc: Record<string, number>, alert) => {
    acc[alert.type] = (acc[alert.type] || 0) + 1;
    return acc;
  }, {});

  const colors = [
    "hsl(var(--chart-1))",
    "hsl(var(--chart-2))",
    "hsl(var(--chart-3))",
    "hsl(var(--chart-4))",
    "hsl(var(--chart-5))",
  ];

  const chartData = Object.entries(grouped).map(([name, value], index) => ({
    name,
    value,
    color: colors[index % colors.length],
  }));

  // fallback if no alerts
  const finalData = chartData.length
    ? chartData
    : [{ name: "No Threats", value: 1, color: "hsl(var(--muted))" }];

  return (
    <Card className="border-border bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="text-foreground">Threat Distribution</CardTitle>
        <p className="text-sm text-muted-foreground">
          Attack types detected
        </p>
      </CardHeader>

      <CardContent>
        <div className="flex items-center gap-6">

          {/* Chart */}
          <ResponsiveContainer width="50%" height={200}>
            <PieChart>
              <Pie
                data={finalData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={5}
                dataKey="value"
              >
                {finalData.map((entry, index) => (
                  <Cell key={index} fill={entry.color} />
                ))}
              </Pie>

              <Tooltip />
            </PieChart>
          </ResponsiveContainer>

          {/* Legend */}
          <div className="flex-1 space-y-3">
            {finalData.map((item, index) => (
              <div key={index} className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-sm">{item.name}</span>
                </div>

                <span className="text-sm text-muted-foreground">
                  {item.value}
                </span>
              </div>
            ))}
          </div>

        </div>
      </CardContent>
    </Card>
  );
}