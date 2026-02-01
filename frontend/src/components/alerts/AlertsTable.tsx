import { useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle, Eye, ExternalLink, ChevronUp, ChevronDown } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { SeverityBadge } from './SeverityBadge';
import type { Alert, AlertSeverity } from '@/types/api';
import { cn } from '@/lib/utils';

interface AlertsTableProps {
  alerts: Alert[];
  onAcknowledge: (id: number) => void;
  onResolve: (id: number) => void;
  isProcessing: boolean;
}

type SortField = 'title' | 'severity' | 'alert_type' | 'created_at' | 'status';
type SortDirection = 'asc' | 'desc';

const severityOrder: Record<AlertSeverity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  info: 4,
};

const alertTypeLabels: Record<string, string> = {
  denial_risk: 'Denial Risk',
  fraud_indicator: 'Fraud Indicator',
  compliance_violation: 'Compliance',
  authorization_expiring: 'Auth Expiring',
  documentation_missing: 'Missing Docs',
  coding_error: 'Coding Error',
  eligibility_issue: 'Eligibility',
  system_anomaly: 'System Anomaly',
};

export function AlertsTable({ alerts, onAcknowledge, onResolve, isProcessing }: AlertsTableProps) {
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const getStatusValue = (alert: Alert) => (alert.is_resolved ? 2 : alert.is_acknowledged ? 1 : 0);

  const sortedAlerts = [...alerts].sort((a, b) => {
    let comparison = 0;

    switch (sortField) {
      case 'title':
        comparison = a.title.localeCompare(b.title);
        break;
      case 'severity':
        comparison = severityOrder[a.severity] - severityOrder[b.severity];
        break;
      case 'alert_type':
        comparison = a.alert_type.localeCompare(b.alert_type);
        break;
      case 'created_at':
        comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        break;
      case 'status':
        comparison = getStatusValue(a) - getStatusValue(b);
        break;
    }

    return sortDirection === 'asc' ? comparison : -comparison;
  });

  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) return null;
    return sortDirection === 'asc' ? (
      <ChevronUp className="h-4 w-4 inline ml-1" />
    ) : (
      <ChevronDown className="h-4 w-4 inline ml-1" />
    );
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return (
      date.toLocaleDateString() +
      ' ' +
      date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    );
  };

  const getStatusBadge = (alert: Alert) => {
    if (alert.is_resolved) {
      return (
        <span className="inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium bg-success-500/10 text-success-500 border-success-500/20">
          Resolved
        </span>
      );
    }
    if (alert.is_acknowledged) {
      return (
        <span className="inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium bg-primary/10 text-primary border-primary/20">
          Acknowledged
        </span>
      );
    }
    return (
      <span className="inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium bg-warning-500/10 text-warning-500 border-warning-500/20">
        Open
      </span>
    );
  };

  if (alerts.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <p className="text-lg font-medium">No alerts found</p>
        <p className="text-sm">Adjust your filters to see more alerts</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead
              className="cursor-pointer hover:bg-muted/50"
              onClick={() => handleSort('title')}
            >
              Title
              {renderSortIcon('title')}
            </TableHead>
            <TableHead
              className="cursor-pointer hover:bg-muted/50"
              onClick={() => handleSort('severity')}
            >
              Severity
              {renderSortIcon('severity')}
            </TableHead>
            <TableHead
              className="cursor-pointer hover:bg-muted/50"
              onClick={() => handleSort('alert_type')}
            >
              Type
              {renderSortIcon('alert_type')}
            </TableHead>
            <TableHead
              className="cursor-pointer hover:bg-muted/50"
              onClick={() => handleSort('created_at')}
            >
              Created
              {renderSortIcon('created_at')}
            </TableHead>
            <TableHead
              className="cursor-pointer hover:bg-muted/50"
              onClick={() => handleSort('status')}
            >
              Status
              {renderSortIcon('status')}
            </TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedAlerts.map((alert) => (
            <TableRow
              key={alert.id}
              className={cn(!alert.is_acknowledged && !alert.is_resolved && 'bg-warning-500/5')}
            >
              <TableCell>
                <div className="space-y-1">
                  <Link
                    to={`/alerts/${alert.id}`}
                    className="font-medium text-foreground hover:text-primary hover:underline"
                  >
                    {alert.title}
                  </Link>
                  <p className="text-sm text-muted-foreground line-clamp-1">{alert.description}</p>
                </div>
              </TableCell>
              <TableCell>
                <SeverityBadge severity={alert.severity} />
              </TableCell>
              <TableCell>
                <span className="text-sm text-muted-foreground">
                  {alertTypeLabels[alert.alert_type] || alert.alert_type}
                </span>
              </TableCell>
              <TableCell>
                <span className="text-sm text-muted-foreground">
                  {formatDate(alert.created_at)}
                </span>
              </TableCell>
              <TableCell>{getStatusBadge(alert)}</TableCell>
              <TableCell>
                <div className="flex items-center justify-end gap-2">
                  {alert.claim && (
                    <Button variant="ghost" size="icon" asChild title="View related claim">
                      <Link to={`/claim-scores/${alert.claim_score}`}>
                        <ExternalLink className="h-4 w-4" />
                      </Link>
                    </Button>
                  )}
                  <Button variant="ghost" size="icon" asChild title="View details">
                    <Link to={`/alerts/${alert.id}`}>
                      <Eye className="h-4 w-4" />
                    </Link>
                  </Button>
                  {!alert.is_acknowledged && !alert.is_resolved && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onAcknowledge(alert.id)}
                      disabled={isProcessing}
                      title="Acknowledge alert"
                    >
                      Ack
                    </Button>
                  )}
                  {!alert.is_resolved && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-success-600 hover:text-success-700 hover:bg-success-500/10"
                      onClick={() => onResolve(alert.id)}
                      disabled={isProcessing}
                      title="Resolve alert"
                    >
                      <CheckCircle className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
