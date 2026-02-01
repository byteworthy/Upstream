import { Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { Dashboard } from '@/pages/Dashboard';

// Placeholder pages - will be implemented in subsequent stories

function ClaimScoresPage() {
  return <div className="text-foreground">Claim Scores - Coming soon</div>;
}

function ClaimScoreDetailPage() {
  return <div className="text-foreground">Claim Score Detail - Coming soon</div>;
}

function WorkQueuePage() {
  return <div className="text-foreground">Work Queue - Coming soon</div>;
}

function AlertsPage() {
  return <div className="text-foreground">Alerts - Coming soon</div>;
}

function AlertDetailPage() {
  return <div className="text-foreground">Alert Detail - Coming soon</div>;
}

function AuthorizationsPage() {
  return <div className="text-foreground">Authorizations - Coming soon</div>;
}

function ExecutionLogPage() {
  return <div className="text-foreground">Execution Log - Coming soon</div>;
}

function SettingsPage() {
  return <div className="text-foreground">Settings - Coming soon</div>;
}

function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-foreground">Login</h1>
        <p className="mt-2 text-muted-foreground">Login page - Coming soon</p>
      </div>
    </div>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<AppLayout />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/claim-scores" element={<ClaimScoresPage />} />
        <Route path="/claim-scores/:id" element={<ClaimScoreDetailPage />} />
        <Route path="/work-queue" element={<WorkQueuePage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/alerts/:id" element={<AlertDetailPage />} />
        <Route path="/authorizations" element={<AuthorizationsPage />} />
        <Route path="/execution-log" element={<ExecutionLogPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
