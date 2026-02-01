import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

function App() {
  return (
    <div className="min-h-screen bg-background p-8">
      <div className="mx-auto max-w-4xl space-y-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-upstream-600 dark:text-upstream-400">
            Upstream Healthcare
          </h1>
          <p className="mt-2 text-muted-foreground">Claims Intelligence Platform - Frontend MVP</p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="text-success-500">Total Claims</CardTitle>
              <CardDescription>Last 30 days</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">12,847</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-warning-500">Denial Rate</CardTitle>
              <CardDescription>Current month</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">4.2%</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-upstream-500">Avg Score</CardTitle>
              <CardDescription>Confidence score</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">87.3</p>
            </CardContent>
          </Card>
        </div>

        <div className="flex justify-center gap-4">
          <Button>Primary Action</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="destructive">Destructive</Button>
        </div>
      </div>
    </div>
  );
}

export default App;
