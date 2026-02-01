import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export function DialysisPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dialysis Intelligence</h1>
        <p className="text-muted-foreground mt-1">
          MA payment variance detection and ESRD monitoring
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>MA Payment Variance</CardTitle>
            <CardDescription>
              Detects when Medicare Advantage pays less than 85% of Traditional Medicare
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Monitoring coming soon...</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>ESRD PPS Drift</CardTitle>
            <CardDescription>Bundle payment rate change detection</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Monitoring coming soon...</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>TDAPA/TPNIES Tracking</CardTitle>
            <CardDescription>Detects missing add-ons for qualifying drugs</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Monitoring coming soon...</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
