import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export function ImagingPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Imaging Center Intelligence</h1>
        <p className="text-muted-foreground mt-1">
          Prior authorization requirements and RBM tracking
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>RBM Requirements</CardTitle>
            <CardDescription>
              Prior auth requirements by Radiology Benefit Manager (eviCore, AIM)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Monitoring coming soon...</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AUC Compliance</CardTitle>
            <CardDescription>CMS Appropriate Use Criteria validation</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Monitoring coming soon...</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Medical Necessity</CardTitle>
            <CardDescription>Documentation completeness scoring</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Monitoring coming soon...</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
