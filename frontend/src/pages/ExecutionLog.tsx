import { useState, useEffect, useCallback } from 'react';
import { Download, Filter, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Timeline, type ExecutionLogEntry } from '@/components/execution/Timeline';

// Generate initial timestamp outside component to avoid react-hooks/purity issues
const getInitialTimestamp = () => Date.now();

// Mock data generator
const generateMockLogs = (baseTimestamp: number): ExecutionLogEntry[] => [
  {
    id: 1,
    action: 'Approved claim for payment',
    action_type: 'auto_execute',
    result: 'success',
    claim_id: 1001,
    claim_score_id: 1,
    user_id: null,
    user_name: null,
    details: {
      confidence_score: 95,
      tier: 1,
      amount: 1250.0,
      payer: 'Blue Cross Blue Shield',
    },
    execution_time_ms: 45,
    created_at: new Date(baseTimestamp - 1 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 2,
    action: 'Queued claim for review',
    action_type: 'queue_review',
    result: 'success',
    claim_id: 1002,
    claim_score_id: 2,
    user_id: null,
    user_name: null,
    details: {
      confidence_score: 72,
      tier: 2,
      review_reason: 'Confidence below auto-execute threshold',
    },
    execution_time_ms: 38,
    created_at: new Date(baseTimestamp - 2 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 3,
    action: 'Manual approval by reviewer',
    action_type: 'manual_override',
    result: 'success',
    claim_id: 1002,
    claim_score_id: 2,
    user_id: 5,
    user_name: 'Sarah Johnson',
    details: {
      override_reason: 'Documentation verified manually',
      original_recommendation: 'queue_review',
    },
    execution_time_ms: 120,
    created_at: new Date(baseTimestamp - 3 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 4,
    action: 'Escalated claim to supervisor',
    action_type: 'escalate',
    result: 'success',
    claim_id: 1003,
    claim_score_id: 3,
    user_id: 5,
    user_name: 'Sarah Johnson',
    details: {
      escalation_reason: 'High dollar amount requires supervisor approval',
      amount: 15000.0,
      supervisor_assigned: 'Michael Chen',
    },
    execution_time_ms: 55,
    created_at: new Date(baseTimestamp - 5 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 5,
    action: 'Auto-execute failed - API timeout',
    action_type: 'auto_execute',
    result: 'failure',
    claim_id: 1004,
    claim_score_id: 4,
    user_id: null,
    user_name: null,
    error_message: 'Connection to payer API timed out after 30 seconds',
    details: {
      payer: 'Aetna',
      retry_count: 3,
      last_error_code: 'ETIMEDOUT',
    },
    execution_time_ms: 30500,
    created_at: new Date(baseTimestamp - 8 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 6,
    action: 'System health check',
    action_type: 'system',
    result: 'success',
    user_id: null,
    user_name: null,
    details: {
      check_type: 'daily_reconciliation',
      claims_processed: 156,
      success_rate: 0.98,
    },
    execution_time_ms: 2500,
    created_at: new Date(baseTimestamp - 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 7,
    action: 'Batch processing skipped',
    action_type: 'system',
    result: 'skipped',
    user_id: null,
    user_name: null,
    details: {
      reason: 'Maintenance window active',
      scheduled_retry: new Date(baseTimestamp + 2 * 60 * 60 * 1000).toISOString(),
    },
    created_at: new Date(baseTimestamp - 26 * 60 * 60 * 1000).toISOString(),
  },
];

export function ExecutionLog() {
  const [baseTimestamp] = useState(getInitialTimestamp);
  const [logs, setLogs] = useState<ExecutionLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    actionType: 'all',
    result: 'all',
    dateRange: '7d',
    search: '',
  });

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 500));
      setLogs(generateMockLogs(baseTimestamp));
    } finally {
      setLoading(false);
    }
  }, [baseTimestamp]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  // Filter logs
  const filteredLogs = logs.filter((log) => {
    if (filters.actionType !== 'all' && log.action_type !== filters.actionType) {
      return false;
    }
    if (filters.result !== 'all' && log.result !== filters.result) {
      return false;
    }
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      const matchesAction = log.action.toLowerCase().includes(searchLower);
      const matchesClaim = log.claim_id?.toString().includes(filters.search);
      const matchesUser = log.user_name?.toLowerCase().includes(searchLower);
      if (!matchesAction && !matchesClaim && !matchesUser) {
        return false;
      }
    }
    return true;
  });

  // Export to CSV
  const handleExport = () => {
    const headers = [
      'ID',
      'Action',
      'Type',
      'Result',
      'Claim ID',
      'User',
      'Timestamp',
      'Execution Time (ms)',
    ];
    const rows = filteredLogs.map((log) => [
      log.id,
      log.action,
      log.action_type,
      log.result,
      log.claim_id || '',
      log.user_name || 'System',
      log.created_at,
      log.execution_time_ms || '',
    ]);

    const csvContent = [headers, ...rows].map((row) => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `execution-log-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Stats
  const stats = {
    total: logs.length,
    success: logs.filter((l) => l.result === 'success').length,
    failure: logs.filter((l) => l.result === 'failure').length,
    pending: logs.filter((l) => l.result === 'pending').length,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Execution Log</h1>
          <p className="text-muted-foreground">View automation execution history and audit trail</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchLogs} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="h-4 w-4 mr-2" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Executions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-foreground">{stats.total}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Successful</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-success-500">{stats.success}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Failed</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-danger-500">{stats.failure}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Success Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-foreground">
              {stats.total > 0 ? ((stats.success / stats.total) * 100).toFixed(1) : 0}%
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Filter className="h-4 w-4" />
            Filters
          </CardTitle>
          <CardDescription>Filter execution logs by type, result, or date range</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-foreground">
                Action Type
              </label>
              <Select
                value={filters.actionType}
                onValueChange={(value: string) => setFilters({ ...filters, actionType: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All types" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="auto_execute">Auto Execute</SelectItem>
                  <SelectItem value="queue_review">Queue Review</SelectItem>
                  <SelectItem value="escalate">Escalate</SelectItem>
                  <SelectItem value="manual_override">Manual Override</SelectItem>
                  <SelectItem value="system">System</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-foreground">Result</label>
              <Select
                value={filters.result}
                onValueChange={(value: string) => setFilters({ ...filters, result: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All results" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Results</SelectItem>
                  <SelectItem value="success">Success</SelectItem>
                  <SelectItem value="failure">Failed</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="skipped">Skipped</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-foreground">Date Range</label>
              <Select
                value={filters.dateRange}
                onValueChange={(value: string) => setFilters({ ...filters, dateRange: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select range" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="24h">Last 24 hours</SelectItem>
                  <SelectItem value="7d">Last 7 days</SelectItem>
                  <SelectItem value="30d">Last 30 days</SelectItem>
                  <SelectItem value="90d">Last 90 days</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-foreground">Search</label>
              <Input
                placeholder="Search by action, claim, or user..."
                value={filters.search}
                onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Timeline */}
      <Card>
        <CardHeader>
          <CardTitle>Execution Timeline</CardTitle>
          <CardDescription>
            Showing {filteredLogs.length} of {logs.length} entries
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Timeline entries={filteredLogs} loading={loading} />
        </CardContent>
      </Card>
    </div>
  );
}
