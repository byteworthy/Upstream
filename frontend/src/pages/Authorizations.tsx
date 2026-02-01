import { useState, useEffect, useCallback } from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { AuthorizationCalendar } from '@/components/authorizations/AuthorizationCalendar';
import { authorizationsApi } from '@/lib/api';
import type { Authorization } from '@/types/api';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

export function Authorizations() {
  const [authorizations, setAuthorizations] = useState<Authorization[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAuthorizations = useCallback(async () => {
    try {
      setLoading(true);
      const response = await authorizationsApi.list({ page_size: 100 });
      setAuthorizations(response.results);
    } catch {
      // Use mock data for development
      const today = new Date();
      setAuthorizations([
        {
          id: 1,
          patient_id: 'PT-001234',
          payer_id: 'PAYER-001',
          authorization_number: 'AUTH-2026-001',
          service_type: 'Skilled Nursing',
          start_date: new Date(today.getTime() - 60 * 24 * 60 * 60 * 1000).toISOString(),
          end_date: new Date(today.getTime() + 3 * 24 * 60 * 60 * 1000).toISOString(),
          authorized_units: 60,
          used_units: 45,
          remaining_units: 15,
          status: 'active',
        },
        {
          id: 2,
          patient_id: 'PT-002345',
          payer_id: 'PAYER-002',
          authorization_number: 'AUTH-2026-002',
          service_type: 'Physical Therapy',
          start_date: new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString(),
          end_date: new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000).toISOString(),
          authorized_units: 24,
          used_units: 18,
          remaining_units: 6,
          status: 'active',
        },
        {
          id: 3,
          patient_id: 'PT-003456',
          payer_id: 'PAYER-001',
          authorization_number: 'AUTH-2026-003',
          service_type: 'Home Health Aide',
          start_date: new Date(today.getTime() - 45 * 24 * 60 * 60 * 1000).toISOString(),
          end_date: new Date(today.getTime() + 10 * 24 * 60 * 60 * 1000).toISOString(),
          authorized_units: 80,
          used_units: 72,
          remaining_units: 8,
          status: 'active',
        },
        {
          id: 4,
          patient_id: 'PT-004567',
          payer_id: 'PAYER-003',
          authorization_number: 'AUTH-2026-004',
          service_type: 'Skilled Nursing',
          start_date: new Date(today.getTime() - 20 * 24 * 60 * 60 * 1000).toISOString(),
          end_date: new Date(today.getTime() + 14 * 24 * 60 * 60 * 1000).toISOString(),
          authorized_units: 40,
          used_units: 20,
          remaining_units: 20,
          status: 'active',
        },
        {
          id: 5,
          patient_id: 'PT-005678',
          payer_id: 'PAYER-002',
          authorization_number: 'AUTH-2026-005',
          service_type: 'Occupational Therapy',
          start_date: new Date(today.getTime() - 10 * 24 * 60 * 60 * 1000).toISOString(),
          end_date: new Date(today.getTime() + 21 * 24 * 60 * 60 * 1000).toISOString(),
          authorized_units: 16,
          used_units: 4,
          remaining_units: 12,
          status: 'active',
        },
        {
          id: 6,
          patient_id: 'PT-006789',
          payer_id: 'PAYER-001',
          authorization_number: 'AUTH-2026-006',
          service_type: 'Speech Therapy',
          start_date: new Date(today.getTime() - 5 * 24 * 60 * 60 * 1000).toISOString(),
          end_date: new Date(today.getTime() + 45 * 24 * 60 * 60 * 1000).toISOString(),
          authorized_units: 12,
          used_units: 2,
          remaining_units: 10,
          status: 'active',
        },
        {
          id: 7,
          patient_id: 'PT-007890',
          payer_id: 'PAYER-003',
          authorization_number: 'AUTH-2026-007',
          service_type: 'Medical Social Services',
          start_date: new Date(today.getTime() - 90 * 24 * 60 * 60 * 1000).toISOString(),
          end_date: new Date(today.getTime() - 5 * 24 * 60 * 60 * 1000).toISOString(),
          authorized_units: 8,
          used_units: 8,
          remaining_units: 0,
          status: 'expired',
        },
        {
          id: 8,
          patient_id: 'PT-008901',
          payer_id: 'PAYER-002',
          authorization_number: 'AUTH-2026-008',
          service_type: 'Physical Therapy',
          start_date: new Date(today.getTime() - 60 * 24 * 60 * 60 * 1000).toISOString(),
          end_date: new Date(today.getTime() + 3 * 24 * 60 * 60 * 1000).toISOString(),
          authorized_units: 20,
          used_units: 20,
          remaining_units: 0,
          status: 'exhausted',
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAuthorizations();
  }, [fetchAuthorizations]);

  const handleExportCSV = () => {
    // Generate CSV content
    const headers = [
      'Authorization Number',
      'Patient ID',
      'Service Type',
      'Start Date',
      'End Date',
      'Authorized Units',
      'Used Units',
      'Remaining Units',
      'Status',
    ];

    const rows = authorizations.map((auth) => [
      auth.authorization_number,
      auth.patient_id,
      auth.service_type,
      auth.start_date.split('T')[0],
      auth.end_date.split('T')[0],
      auth.authorized_units,
      auth.used_units,
      auth.remaining_units,
      auth.status,
    ]);

    const csvContent = [headers.join(','), ...rows.map((row) => row.join(','))].join('\n');

    // Download file
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `authorizations-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    toast.success('CSV exported successfully');
  };

  if (loading && authorizations.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading authorizations...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Authorizations</h1>
          <p className="text-muted-foreground">Track authorization expiration dates and usage</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchAuthorizations} disabled={loading}>
          <RefreshCw className={cn('h-4 w-4 mr-2', loading && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {/* Calendar Component */}
      <AuthorizationCalendar authorizations={authorizations} onExportCSV={handleExportCSV} />
    </div>
  );
}
