import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Upload } from "lucide-react";

export default function Insights() {
  const metrics = [
    { label: "Accuracy", value: "98.7%" },
    { label: "Precision", value: "97.3%" },
    { label: "Recall", value: "96.8%" },
    { label: "F1 Score", value: "97.0%" },
  ];

  const confusionMatrix = [
    [450, 12],
    [15, 523],
  ];

  return (
    <div className="space-y-6">
      <Card className="border-border bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-foreground">Model Performance</CardTitle>
              <p className="text-sm text-muted-foreground mt-1">Real-time ML model metrics</p>
            </div>
            <Select defaultValue="random-forest">
              <SelectTrigger className="w-48 bg-background/50">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="random-forest">Random Forest</SelectItem>
                <SelectItem value="svm">Support Vector Machine</SelectItem>
                <SelectItem value="neural-net">Neural Network</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {metrics.map((metric, index) => (
              <div key={index} className="p-4 rounded-lg bg-gradient-cyber border border-primary/30">
                <p className="text-sm text-muted-foreground mb-1">{metric.label}</p>
                <p className="text-2xl font-bold text-foreground">{metric.value}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-border bg-card/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-foreground">Confusion Matrix</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-2 text-sm">
                <div></div>
                <div className="text-center font-medium text-muted-foreground">Predicted Normal</div>
                <div className="text-center font-medium text-muted-foreground">Predicted Malicious</div>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div className="flex items-center font-medium text-muted-foreground text-sm">Actual Normal</div>
                <div className="bg-success/20 border border-success/30 rounded-lg p-6 text-center">
                  <span className="text-2xl font-bold text-foreground">{confusionMatrix[0][0]}</span>
                </div>
                <div className="bg-destructive/20 border border-destructive/30 rounded-lg p-6 text-center">
                  <span className="text-2xl font-bold text-foreground">{confusionMatrix[0][1]}</span>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div className="flex items-center font-medium text-muted-foreground text-sm">Actual Malicious</div>
                <div className="bg-destructive/20 border border-destructive/30 rounded-lg p-6 text-center">
                  <span className="text-2xl font-bold text-foreground">{confusionMatrix[1][0]}</span>
                </div>
                <div className="bg-success/20 border border-success/30 rounded-lg p-6 text-center">
                  <span className="text-2xl font-bold text-foreground">{confusionMatrix[1][1]}</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-card/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-foreground">Test Custom Dataset</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-primary/50 transition-colors cursor-pointer">
                <Upload className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-sm text-foreground mb-1">Upload PCAP or CSV file</p>
                <p className="text-xs text-muted-foreground">Max file size: 50MB</p>
              </div>
              <Button className="w-full" variant="outline">
                Analyze Dataset
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
