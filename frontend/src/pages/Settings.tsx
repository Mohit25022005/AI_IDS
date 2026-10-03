import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import { api } from "@/lib/api";

interface IdsSettings {
  live_detection: boolean;
  ml_model: string;
  sensitivity_threshold: number;
  auto_retrain: boolean;
  email_alerts: boolean;
  desktop_notifications: boolean;
}

const DEFAULT_SETTINGS: IdsSettings = {
  live_detection: true,
  ml_model: "random-forest",
  sensitivity_threshold: 75,
  auto_retrain: false,
  email_alerts: false,
  desktop_notifications: false,
};

const MODEL_OPTIONS = [
  { value: "random-forest",  label: "Random Forest" },
  { value: "svm",            label: "Support Vector Machine" },
  { value: "neural-network", label: "Neural Network (MLP)" },
  { value: "hybrid",         label: "Hybrid Ensemble (RF + SVM + NN)" },
];

export default function Settings() {
  const { toast } = useToast();
  const [settings, setSettings] = useState<IdsSettings>(DEFAULT_SETTINGS);
  const [modelInfo, setModelInfo] = useState<{ training_timestamp?: string; n_train_samples?: number } | null>(null);

  useEffect(() => {
    api.get("/settings").then((r) => setSettings(r.data)).catch(console.error);
  }, []);

  useEffect(() => {
    api.get("/model/info").then((r) => setModelInfo(r.data)).catch(() => setModelInfo(null));
  }, [settings.ml_model]);

  const updateSetting = async (key: keyof IdsSettings, value: boolean | string | number) => {
    const next = { ...settings, [key]: value };
    setSettings(next);
    try {
      await api.post("/settings", { [key]: value });
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Error",
        description: err?.response?.data?.error ?? "Failed to update setting",
      });
    }
  };

  const handleModelAction = async (action: "retrain" | "reload" | "reset") => {
    try {
      const res = await api.post(`/model/${action}`);
      toast({ title: "Success", description: res.data.message });
      if (action === "reset") {
        const s = await api.get("/settings");
        setSettings(s.data);
      }
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Error",
        description: err?.response?.data?.error ?? "Model action failed",
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
            <div>
              <Label htmlFor="live-detection" className="text-foreground">Live Detection</Label>
              <p className="text-sm text-muted-foreground">Enable real-time threat detection</p>
            </div>
            <Switch
              id="live-detection"
              checked={settings.live_detection}
              onCheckedChange={(v) => updateSetting("live_detection", v)}
            />
          </div>

          <div className="space-y-2">
            <Label className="text-foreground">Active ML Model</Label>
            <Select
              value={settings.ml_model}
              onValueChange={(v) => updateSetting("ml_model", v)}
            >
              <SelectTrigger className="bg-background/50">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MODEL_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {modelInfo && (
              <p className="text-xs text-muted-foreground mt-1">
                Trained:{" "}
                {modelInfo.training_timestamp
                  ? new Date(modelInfo.training_timestamp).toLocaleString()
                  : "—"}
                {modelInfo.n_train_samples != null &&
                  ` · ${modelInfo.n_train_samples} training samples`}
              </p>
            )}
          </div>

          <div className="space-y-3">
            <div className="flex justify-between">
              <Label className="text-foreground">Sensitivity Threshold</Label>
              <span className="text-sm text-muted-foreground">
                {settings.sensitivity_threshold}%
              </span>
            </div>
            <Slider
              value={[settings.sensitivity_threshold]}
              max={100}
              step={1}
              onValueChange={([v]) => updateSetting("sensitivity_threshold", v)}
            />
            <p className="text-xs text-muted-foreground">
              Minimum confidence required to generate an alert
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
            <div>
              <Label className="text-foreground">Auto-Retrain</Label>
              <p className="text-sm text-muted-foreground">
                Not yet implemented — retrain manually via train_model.py
              </p>
            </div>
            <Switch
              checked={settings.auto_retrain}
              onCheckedChange={(v) => updateSetting("auto_retrain", v)}
              disabled
            />
          </div>
          <div className="pt-4 border-t border-border space-y-3">
            <Button className="w-full" variant="outline"
              onClick={() => handleModelAction("reload")}>
              Reload Model Artifacts
            </Button>
            <Button className="w-full" variant="destructive"
              onClick={() => handleModelAction("reset")}>
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
          {[
            { id: "email-alerts",          key: "email_alerts"          as const, label: "Email Alerts",          desc: "Reserved for future integration" },
            { id: "desktop-notifications", key: "desktop_notifications" as const, label: "Desktop Notifications", desc: "Reserved for future integration" },
          ].map(({ id, key, label, desc }) => (
            <div key={id} className="flex items-center justify-between">
              <div>
                <Label htmlFor={id} className="text-foreground">{label}</Label>
                <p className="text-sm text-muted-foreground">{desc}</p>
              </div>
              <Switch
                id={id}
                checked={settings[key] as boolean}
                onCheckedChange={(v) => updateSetting(key, v)}
              />
            </div>
          ))}
        </CardContent>
      </Card>

    </div>
  );
}
