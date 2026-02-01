import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Bell, AlertTriangle, Info } from "lucide-react";

export function Alerts() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Alerts</h2>
        <Button variant="outline">Mark All Read</Button>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Active Alerts</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-4 text-muted-foreground">
            Alerts and notifications placeholder. This will display system alerts and notifications.
          </p>
          <div className="space-y-2">
            <div className="flex items-start gap-3 rounded-md border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950">
              <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400" />
              <div className="flex-1">
                <p className="font-medium text-red-800 dark:text-red-200">Critical: High denial rate detected</p>
                <p className="text-sm text-red-600 dark:text-red-400">
                  Claims denial rate has exceeded 15% threshold
                </p>
                <p className="text-xs text-red-500 dark:text-red-500">2 hours ago</p>
              </div>
            </div>
            <div className="flex items-start gap-3 rounded-md border border-yellow-200 bg-yellow-50 p-3 dark:border-yellow-900 dark:bg-yellow-950">
              <Bell className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
              <div className="flex-1">
                <p className="font-medium text-yellow-800 dark:text-yellow-200">Warning: Processing queue backup</p>
                <p className="text-sm text-yellow-600 dark:text-yellow-400">
                  89 claims pending review for more than 24 hours
                </p>
                <p className="text-xs text-yellow-500 dark:text-yellow-500">5 hours ago</p>
              </div>
            </div>
            <div className="flex items-start gap-3 rounded-md border border-blue-200 bg-blue-50 p-3 dark:border-blue-900 dark:bg-blue-950">
              <Info className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              <div className="flex-1">
                <p className="font-medium text-blue-800 dark:text-blue-200">Info: System maintenance scheduled</p>
                <p className="text-sm text-blue-600 dark:text-blue-400">
                  Planned maintenance window: Feb 15, 2026 02:00-04:00 UTC
                </p>
                <p className="text-xs text-blue-500 dark:text-blue-500">1 day ago</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
