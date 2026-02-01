import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function Claims() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Claims</h2>
        <Button>New Claim</Button>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Claims List</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            Claims management placeholder. This will display a searchable, filterable list of claims.
          </p>
          <div className="mt-4 space-y-2">
            <div className="flex items-center justify-between rounded-md border p-3">
              <div>
                <p className="font-medium">Claim #12345</p>
                <p className="text-sm text-muted-foreground">Submitted: Jan 15, 2026</p>
              </div>
              <span className="rounded-full bg-yellow-100 px-2 py-1 text-xs text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
                Pending
              </span>
            </div>
            <div className="flex items-center justify-between rounded-md border p-3">
              <div>
                <p className="font-medium">Claim #12344</p>
                <p className="text-sm text-muted-foreground">Submitted: Jan 14, 2026</p>
              </div>
              <span className="rounded-full bg-green-100 px-2 py-1 text-xs text-green-800 dark:bg-green-900 dark:text-green-200">
                Approved
              </span>
            </div>
            <div className="flex items-center justify-between rounded-md border p-3">
              <div>
                <p className="font-medium">Claim #12343</p>
                <p className="text-sm text-muted-foreground">Submitted: Jan 13, 2026</p>
              </div>
              <span className="rounded-full bg-red-100 px-2 py-1 text-xs text-red-800 dark:bg-red-900 dark:text-red-200">
                Denied
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
