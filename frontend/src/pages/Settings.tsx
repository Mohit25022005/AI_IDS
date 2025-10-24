import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";

export default function Settings() {
  return (
    <div className="space-y-6 max-w-3xl">
      <Card className="border-border bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-foreground">Detection Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="live-detection" className="text-foreground">Live Detection</Label>
              <p className="text-sm text-muted-foreground">Enable real-time threat detection</p>
            </div>
            <Switch id="live-detection" defaultChecked />
          </div>

          <div className="space-y-2">
            <Label className="text-foreground">ML Model</Label>
            <Select defaultValue="random-forest">
              <SelectTrigger className="bg-background/50">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="random-forest">Random Forest</SelectItem>
                <SelectItem value="svm">Support Vector Machine</SelectItem>
                <SelectItem value="neural-net">Neural Network</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-3">
            <div className="flex justify-between">
              <Label className="text-foreground">Sensitivity Threshold</Label>
              <span className="text-sm text-muted-foreground">75%</span>
            </div>
            <Slider defaultValue={[75]} max={100} step={1} />
            <p className="text-xs text-muted-foreground">
              Higher values increase detection rate but may produce more false positives
            </p>
          </div>
        </CardContent>
      </Card>

      <Card className="border-border bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-foreground">Model Management</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-foreground">Auto-Retrain</Label>
              <p className="text-sm text-muted-foreground">Automatically retrain model with new data</p>
            </div>
            <Switch id="auto-retrain" />
          </div>

          <div className="pt-4 border-t border-border space-y-3">
            <Button className="w-full" variant="outline">
              Retrain Model
            </Button>
            <Button className="w-full" variant="outline">
              Reload Model
            </Button>
            <Button className="w-full" variant="destructive">
              Reset to Defaults
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="border-border bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-foreground">Notifications</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-foreground">Email Alerts</Label>
              <p className="text-sm text-muted-foreground">Receive email notifications for threats</p>
            </div>
            <Switch id="email-alerts" defaultChecked />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-foreground">Desktop Notifications</Label>
              <p className="text-sm text-muted-foreground">Show browser notifications</p>
            </div>
            <Switch id="desktop-notifications" defaultChecked />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
