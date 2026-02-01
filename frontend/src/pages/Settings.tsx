import { useState, useEffect } from 'react';
import { Save, RotateCcw, Settings2, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ThresholdSlider } from '@/components/settings/ThresholdSlider';
import { ActionToggle } from '@/components/settings/ActionToggle';
import { toast } from 'sonner';

interface AutomationSettings {
  automationStage: 'learning' | 'assisted' | 'supervised' | 'autonomous';
  autoExecuteConfidence: number;
  queueReviewMinConfidence: number;
  autoExecuteMaxAmount: number;
  escalateMinAmount: number;
  actions: {
    autoApprove: boolean;
    autoReject: boolean;
    autoEscalate: boolean;
    sendAlerts: boolean;
    createAuditLog: boolean;
  };
}

const defaultSettings: AutomationSettings = {
  automationStage: 'supervised',
  autoExecuteConfidence: 90,
  queueReviewMinConfidence: 70,
  autoExecuteMaxAmount: 5000,
  escalateMinAmount: 10000,
  actions: {
    autoApprove: true,
    autoReject: false,
    autoEscalate: true,
    sendAlerts: true,
    createAuditLog: true,
  },
};

const stageDescriptions: Record<string, string> = {
  learning: 'System observes only - no automated actions taken',
  assisted: 'System suggests actions but requires human confirmation',
  supervised: 'System executes high-confidence actions, queues others for review',
  autonomous: 'System executes all actions within thresholds automatically',
};

export function Settings() {
  const [settings, setSettings] = useState<AutomationSettings>(defaultSettings);
  const [originalSettings, setOriginalSettings] = useState<AutomationSettings>(defaultSettings);
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    // Load settings from API
    const loadSettings = async () => {
      try {
        // Simulate API call
        await new Promise((resolve) => setTimeout(resolve, 300));
        // Use default settings for now
        setSettings(defaultSettings);
        setOriginalSettings(defaultSettings);
      } catch {
        toast.error('Failed to load settings');
      }
    };

    loadSettings();
  }, []);

  useEffect(() => {
    // Check if settings have changed
    setHasChanges(JSON.stringify(settings) !== JSON.stringify(originalSettings));
  }, [settings, originalSettings]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 500));
      setOriginalSettings(settings);
      toast.success('Settings saved successfully');
    } catch {
      toast.error('Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setSettings(originalSettings);
    toast.info('Changes discarded');
  };

  const handleResetToDefaults = () => {
    setSettings(defaultSettings);
    toast.info('Reset to default values');
  };

  const updateAction = (key: keyof AutomationSettings['actions'], value: boolean) => {
    setSettings({
      ...settings,
      actions: {
        ...settings.actions,
        [key]: value,
      },
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Automation Settings</h1>
          <p className="text-muted-foreground">Configure automation thresholds and behaviors</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleResetToDefaults}>
            <RotateCcw className="h-4 w-4 mr-2" />
            Reset to Defaults
          </Button>
          {hasChanges && (
            <>
              <Button variant="outline" size="sm" onClick={handleReset}>
                Discard Changes
              </Button>
              <Button size="sm" onClick={handleSave} disabled={isSaving}>
                <Save className="h-4 w-4 mr-2" />
                {isSaving ? 'Saving...' : 'Save Changes'}
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Unsaved Changes Warning */}
      {hasChanges && (
        <div className="flex items-center gap-2 p-3 bg-warning-500/10 border border-warning-500/20 rounded-lg">
          <AlertTriangle className="h-4 w-4 text-warning-500" />
          <span className="text-sm text-warning-500">You have unsaved changes</span>
        </div>
      )}

      {/* Automation Stage */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings2 className="h-5 w-5" />
            Automation Stage
          </CardTitle>
          <CardDescription>Control the level of automation for claim processing</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium text-foreground mb-1.5 block">
              Current Stage
            </label>
            <Select
              value={settings.automationStage}
              onValueChange={(value: string) =>
                setSettings({
                  ...settings,
                  automationStage: value as AutomationSettings['automationStage'],
                })
              }
            >
              <SelectTrigger className="w-full sm:w-[300px]">
                <SelectValue placeholder="Select automation stage" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="learning">Learning Mode</SelectItem>
                <SelectItem value="assisted">Assisted Mode</SelectItem>
                <SelectItem value="supervised">Supervised Mode</SelectItem>
                <SelectItem value="autonomous">Autonomous Mode</SelectItem>
              </SelectContent>
            </Select>
            <p className="mt-2 text-sm text-muted-foreground">
              {stageDescriptions[settings.automationStage]}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Confidence Thresholds */}
      <Card>
        <CardHeader>
          <CardTitle>Confidence Thresholds</CardTitle>
          <CardDescription>Set minimum confidence levels for automated actions</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <ThresholdSlider
            label="Auto-Execute Confidence"
            description="Minimum confidence score for automatic claim processing"
            value={settings.autoExecuteConfidence}
            min={50}
            max={100}
            onChange={(value) => setSettings({ ...settings, autoExecuteConfidence: value })}
            showTicks
          />

          <ThresholdSlider
            label="Queue Review Minimum Confidence"
            description="Claims below this threshold are queued for manual review"
            value={settings.queueReviewMinConfidence}
            min={30}
            max={90}
            onChange={(value) => setSettings({ ...settings, queueReviewMinConfidence: value })}
            showTicks
          />

          {settings.autoExecuteConfidence <= settings.queueReviewMinConfidence && (
            <div className="flex items-center gap-2 p-3 bg-danger-500/10 border border-danger-500/20 rounded-lg">
              <AlertTriangle className="h-4 w-4 text-danger-500" />
              <span className="text-sm text-danger-500">
                Auto-execute threshold should be higher than queue review threshold
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Amount Thresholds */}
      <Card>
        <CardHeader>
          <CardTitle>Amount Thresholds</CardTitle>
          <CardDescription>Set dollar amount limits for automated processing</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="text-sm font-medium text-foreground mb-1.5 block">
                Auto-Execute Max Amount
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                  $
                </span>
                <Input
                  type="number"
                  min={0}
                  max={100000}
                  value={settings.autoExecuteMaxAmount}
                  onChange={(e) =>
                    setSettings({ ...settings, autoExecuteMaxAmount: Number(e.target.value) })
                  }
                  className="pl-7"
                />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Claims above this amount require manual approval
              </p>
            </div>

            <div>
              <label className="text-sm font-medium text-foreground mb-1.5 block">
                Escalate Min Amount
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                  $
                </span>
                <Input
                  type="number"
                  min={0}
                  max={1000000}
                  value={settings.escalateMinAmount}
                  onChange={(e) =>
                    setSettings({ ...settings, escalateMinAmount: Number(e.target.value) })
                  }
                  className="pl-7"
                />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Claims above this amount are escalated to supervisors
              </p>
            </div>
          </div>

          {settings.escalateMinAmount <= settings.autoExecuteMaxAmount && (
            <div className="flex items-center gap-2 p-3 bg-warning-500/10 border border-warning-500/20 rounded-lg">
              <AlertTriangle className="h-4 w-4 text-warning-500" />
              <span className="text-sm text-warning-500">
                Escalate amount should typically be higher than auto-execute max amount
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Action Toggles */}
      <Card>
        <CardHeader>
          <CardTitle>Enabled Actions</CardTitle>
          <CardDescription>Enable or disable specific automated actions</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <ActionToggle
            label="Auto-Approve Claims"
            description="Automatically approve high-confidence claims within amount limits"
            checked={settings.actions.autoApprove}
            onChange={(checked) => updateAction('autoApprove', checked)}
          />

          <ActionToggle
            label="Auto-Reject Claims"
            description="Automatically reject claims with clear denial indicators"
            checked={settings.actions.autoReject}
            onChange={(checked) => updateAction('autoReject', checked)}
          />

          <ActionToggle
            label="Auto-Escalate"
            description="Automatically escalate high-value or complex claims"
            checked={settings.actions.autoEscalate}
            onChange={(checked) => updateAction('autoEscalate', checked)}
          />

          <ActionToggle
            label="Send Alerts"
            description="Send real-time alerts for important events"
            checked={settings.actions.sendAlerts}
            onChange={(checked) => updateAction('sendAlerts', checked)}
          />

          <ActionToggle
            label="Create Audit Log"
            description="Log all automated actions for compliance tracking"
            checked={settings.actions.createAuditLog}
            onChange={(checked) => updateAction('createAuditLog', checked)}
          />
        </CardContent>
      </Card>

      {/* Save Button (Mobile) */}
      {hasChanges && (
        <div className="fixed bottom-4 left-4 right-4 sm:hidden">
          <Button className="w-full" onClick={handleSave} disabled={isSaving}>
            <Save className="h-4 w-4 mr-2" />
            {isSaving ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>
      )}
    </div>
  );
}
