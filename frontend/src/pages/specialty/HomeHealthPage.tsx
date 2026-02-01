import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export function HomeHealthPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Home Health Intelligence</h1>
        <p className="text-muted-foreground mt-1">PDGM validation and Face-to-Face tracking</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>PDGM Grouper</CardTitle>
            <CardDescription>432+ grouping combination validation</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Monitoring coming soon...</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Face-to-Face Timing</CardTitle>
            <CardDescription>Within 90 days encounter validation</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Monitoring coming soon...</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>NOA Deadlines</CardTitle>
            <CardDescription>Notice of Admission submission window tracking</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Monitoring coming soon...</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
