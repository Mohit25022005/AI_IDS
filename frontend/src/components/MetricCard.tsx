import { LucideIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: string;
  variant?: "default" | "success" | "warning" | "danger";
}

export default function MetricCard({ title, value, icon: Icon, trend, variant = "default" }: MetricCardProps) {
  const variantStyles = {
    default: "bg-gradient-cyber border-primary/30",
    success: "bg-gradient-safe border-success/30",
    warning: "bg-warning/10 border-warning/30",
    danger: "bg-gradient-threat border-destructive/30",
  };

  const iconColors = {
    default: "text-primary",
    success: "text-success",
    warning: "text-warning",
    danger: "text-destructive",
  };

  return (
    <Card className={`border ${variantStyles[variant]} backdrop-blur-sm transition-all hover:scale-105`}>
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className={`w-12 h-12 rounded-lg bg-card/50 flex items-center justify-center ${iconColors[variant]}`}>
            <Icon className="h-6 w-6" />
          </div>
          {trend && (
            <span className="text-xs font-medium text-muted-foreground">{trend}</span>
          )}
        </div>
        <div>
          <p className="text-sm text-muted-foreground mb-1">{title}</p>
          <p className="text-3xl font-bold text-foreground">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}
