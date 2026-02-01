import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export function ABAPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">ABA Therapy Intelligence</h1>
        <p className="text-muted-foreground mt-1">
          Authorization tracking and unit consumption monitoring
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Authorization Cycle</CardTitle>
            <CardDescription>
              30/14/3 day expiration alerts for prior authorizations
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Monitoring coming soon...</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Visit Exhaustion</CardTitle>
            <CardDescription>Predicts when authorized units will run out</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Monitoring coming soon...</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>BCBA Credentials</CardTitle>
            <CardDescription>Supervisor credential expiration tracking</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Monitoring coming soon...</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
