import { Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { Dashboard } from '@/pages/Dashboard';
import { ClaimScores } from '@/pages/ClaimScores';
import { ClaimScoreDetail } from '@/pages/ClaimScoreDetail';
import { WorkQueue } from '@/pages/WorkQueue';
import { Alerts } from '@/pages/Alerts';
import { AlertDetail } from '@/pages/AlertDetail';
import { Authorizations } from '@/pages/Authorizations';

// Placeholder pages - will be implemented in subsequent stories

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
        <Route path="/claim-scores" element={<ClaimScores />} />
        <Route path="/claim-scores/:id" element={<ClaimScoreDetail />} />
        <Route path="/work-queue" element={<WorkQueue />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/alerts/:id" element={<AlertDetail />} />
        <Route path="/authorizations" element={<Authorizations />} />
        <Route path="/execution-log" element={<ExecutionLogPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
