import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export function PTOTPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">PT/OT Intelligence</h1>
        <p className="text-muted-foreground mt-1">8-minute rule validation and G-code tracking</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>8-Minute Rule</CardTitle>
            <CardDescription>Time-based billing unit validation</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Monitoring coming soon...</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>G-Code Validation</CardTitle>
            <CardDescription>Functional limitation reporting compliance</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Monitoring coming soon...</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Certification Periods</CardTitle>
            <CardDescription>Plan of care recertification tracking</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Monitoring coming soon...</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
