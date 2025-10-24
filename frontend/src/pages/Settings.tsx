import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import { api } from "@/lib/api";

export default function Settings() {
  const { toast } = useToast();
  const [settings, setSettings] = useState({
    live_detection: true,
    ml_model: "random-forest",
    sensitivity_threshold: 75,
    auto_retrain: false,
    email_alerts: true,
    desktop_notifications: true,
  });

  // Fetch settings from backend
  useEffect(() => {
    api.get("/settings").then(res => setSettings(res.data)).catch(console.error);
  }, []);

  // Update single setting
  const updateSetting = async (key, value) => {
    const newSettings = { ...settings, [key]: value };
    setSettings(newSettings);
    try {
      await api.post("/settings", { [key]: value });
    } catch (err) {
      console.error(err);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to update setting",
      });
    }
  };

  // Model management actions
  const handleModelAction = async (action) => {
    try {
      const res = await api.post(`/model/${action}`);
      toast({
        title: "Success",
        description: res.data.message,
      });
      // Reload settings after reset
      if (action === "reset") {
        const settingsRes = await api.get("/settings");
        setSettings(settingsRes.data);
      }
    } catch (err) {
      console.error(err);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Model action failed",
      });
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Detection Settings */}
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
            <Switch
              id="live-detection"
              checked={settings.live_detection}
              onCheckedChange={(val) => updateSetting("live_detection", val)}
            />
          </div>

          <div className="space-y-2">
            <Label className="text-foreground">ML Model</Label>
            <Select
              value={settings.ml_model}
              onValueChange={(val) => updateSetting("ml_model", val)}
            >
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
              <span className="text-sm text-muted-foreground">{settings.sensitivity_threshold}%</span>
            </div>
            <Slider
              value={[settings.sensitivity_threshold]}
              max={100}
              step={1}
              onValueChange={(val) => updateSetting("sensitivity_threshold", val[0])}
            />
            <p className="text-xs text-muted-foreground">
              Higher values increase detection rate but may produce more false positives
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Model Management */}
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
            <Switch
              id="auto-retrain"
              checked={settings.auto_retrain}
              onCheckedChange={(val) => updateSetting("auto_retrain", val)}
            />
          </div>

          <div className="pt-4 border-t border-border space-y-3">
            <Button className="w-full" variant="outline" onClick={() => handleModelAction("retrain")}>
              Retrain Model
            </Button>
            <Button className="w-full" variant="outline" onClick={() => handleModelAction("reload")}>
              Reload Model
            </Button>
            <Button className="w-full" variant="destructive" onClick={() => handleModelAction("reset")}>
              Reset to Defaults
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Notifications */}
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
            <Switch
              id="email-alerts"
              checked={settings.email_alerts}
              onCheckedChange={(val) => updateSetting("email_alerts", val)}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-foreground">Desktop Notifications</Label>
              <p className="text-sm text-muted-foreground">Show browser notifications</p>
            </div>
            <Switch
              id="desktop-notifications"
              checked={settings.desktop_notifications}
              onCheckedChange={(val) => updateSetting("desktop_notifications", val)}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
