import { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Filter, SortAsc, SortDesc } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { QueueItem } from '@/components/queue/QueueItem';
import { BulkActions } from '@/components/queue/BulkActions';
import { workQueueApi } from '@/lib/api';
import type { WorkQueueItem } from '@/types/api';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

type SortField = 'priority' | 'confidence' | 'amount' | 'created_at';
type SortDirection = 'asc' | 'desc';

const priorityOrder = { high: 0, medium: 1, low: 2 };

export function WorkQueue() {
  const [items, setItems] = useState<WorkQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [isProcessing, setIsProcessing] = useState(false);
  const [sortField, setSortField] = useState<SortField>('priority');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [priorityFilter, setPriorityFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all');

  const fetchItems = useCallback(async () => {
    try {
      setLoading(true);
      const response = await workQueueApi.list({
        ordering: sortDirection === 'desc' ? `-${sortField}` : sortField,
      });
      setItems(response.results);
    } catch {
      // Use mock data for development
      setItems([
        {
          id: 1,
          claim_id: 'CLM-000123',
          claim_score_id: 123,
          confidence: 72.5,
          amount: 4500.0,
          priority: 'high',
          reason:
            'Documentation confidence below threshold (68.2%). Verify supporting documents before approval.',
          created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          id: 2,
          claim_id: 'CLM-000456',
          claim_score_id: 456,
          confidence: 65.8,
          amount: 12000.0,
          priority: 'high',
          reason:
            'High claim amount ($12,000) with moderate confidence. Requires senior review before processing.',
          created_at: new Date(Date.now() - 26 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          id: 3,
          claim_id: 'CLM-000789',
          claim_score_id: 789,
          confidence: 78.3,
          amount: 2800.0,
          priority: 'medium',
          reason: 'Medical necessity confidence at 71.5%. Review clinical documentation.',
          created_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          id: 4,
          claim_id: 'CLM-001012',
          claim_score_id: 1012,
          confidence: 81.2,
          amount: 1500.0,
          priority: 'medium',
          reason: 'New provider with limited history. Verify credentials and service details.',
          created_at: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          id: 5,
          claim_id: 'CLM-001345',
          claim_score_id: 1345,
          confidence: 85.1,
          amount: 950.0,
          priority: 'low',
          reason: 'Minor coding discrepancy detected. Quick verification recommended.',
          created_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          id: 6,
          claim_id: 'CLM-001678',
          claim_score_id: 1678,
          confidence: 74.9,
          amount: 3200.0,
          priority: 'medium',
          reason: 'Authorization expiring soon. Confirm coverage dates.',
          created_at: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [sortField, sortDirection]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  // Sort and filter items
  const processedItems = items
    .filter((item) => priorityFilter === 'all' || item.priority === priorityFilter)
    .sort((a, b) => {
      let comparison = 0;

      switch (sortField) {
        case 'priority':
          comparison = priorityOrder[a.priority] - priorityOrder[b.priority];
          break;
        case 'confidence':
          comparison = a.confidence - b.confidence;
          break;
        case 'amount':
          comparison = a.amount - b.amount;
          break;
        case 'created_at':
          comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
          break;
      }

      return sortDirection === 'asc' ? comparison : -comparison;
    });

  const handleSelect = (id: number, selected: boolean) => {
    setSelectedIds((prev) => {
      const newSet = new Set(prev);
      if (selected) {
        newSet.add(id);
      } else {
        newSet.delete(id);
      }
      return newSet;
    });
  };

  const handleSelectAll = () => {
    if (selectedIds.size === processedItems.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(processedItems.map((item) => item.id)));
    }
  };

  const handleClearSelection = () => {
    setSelectedIds(new Set());
  };

  const handleAction = async (id: number, action: 'approve' | 'reject' | 'escalate') => {
    try {
      setIsProcessing(true);
      switch (action) {
        case 'approve':
          await workQueueApi.approve(id);
          toast.success('Claim approved successfully');
          break;
        case 'reject':
          await workQueueApi.reject(id);
          toast.success('Claim rejected');
          break;
        case 'escalate':
          await workQueueApi.escalate(id);
          toast.success('Claim escalated to senior reviewer');
          break;
      }
      // Remove item from list
      setItems((prev) => prev.filter((item) => item.id !== id));
      setSelectedIds((prev) => {
        const newSet = new Set(prev);
        newSet.delete(id);
        return newSet;
      });
    } catch {
      toast.error(`Failed to ${action} claim`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleBulkAction = async (action: 'approve' | 'reject' | 'escalate') => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;

    try {
      setIsProcessing(true);
      switch (action) {
        case 'approve':
          await workQueueApi.bulkApprove(ids);
          toast.success(`${ids.length} claims approved`);
          break;
        case 'reject':
          await workQueueApi.bulkReject(ids);
          toast.success(`${ids.length} claims rejected`);
          break;
        case 'escalate':
          await workQueueApi.bulkEscalate(ids);
          toast.success(`${ids.length} claims escalated`);
          break;
      }
      // Remove items from list
      setItems((prev) => prev.filter((item) => !selectedIds.has(item.id)));
      setSelectedIds(new Set());
    } catch {
      toast.error(`Failed to ${action} claims`);
    } finally {
      setIsProcessing(false);
    }
  };

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const SortIcon = sortDirection === 'asc' ? SortAsc : SortDesc;

  if (loading && items.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading work queue...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Work Queue</h1>
          <p className="text-muted-foreground">
            Review and process claims requiring human decision ({processedItems.length} items)
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchItems} disabled={loading}>
          <RefreshCw className={cn('h-4 w-4 mr-2', loading && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {/* Filters and Sort */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Filters & Sorting</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-4">
            {/* Priority Filter */}
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Priority:</span>
              <div className="flex gap-1">
                {(['all', 'high', 'medium', 'low'] as const).map((priority) => (
                  <Button
                    key={priority}
                    variant={priorityFilter === priority ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setPriorityFilter(priority)}
                    className="capitalize"
                  >
                    {priority}
                  </Button>
                ))}
              </div>
            </div>

            {/* Sort */}
            <div className="flex items-center gap-2 ml-auto">
              <span className="text-sm font-medium">Sort by:</span>
              <div className="flex gap-1">
                {(['priority', 'confidence', 'amount', 'created_at'] as const).map((field) => (
                  <Button
                    key={field}
                    variant={sortField === field ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => toggleSort(field)}
                    className="capitalize"
                  >
                    {field.replace('_', ' ')}
                    {sortField === field && <SortIcon className="h-3 w-3 ml-1" />}
                  </Button>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Bulk Actions */}
      <BulkActions
        selectedCount={selectedIds.size}
        onAction={handleBulkAction}
        onClearSelection={handleClearSelection}
        isProcessing={isProcessing}
      />

      {/* Queue Items */}
      {processedItems.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <div className="text-center text-muted-foreground">
              <p className="text-lg font-medium">No items in queue</p>
              <p className="text-sm">
                {priorityFilter !== 'all'
                  ? `No ${priorityFilter} priority items found`
                  : 'All claims have been processed'}
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {/* Select All */}
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Button variant="ghost" size="sm" onClick={handleSelectAll}>
              {selectedIds.size === processedItems.length ? 'Deselect All' : 'Select All'}
            </Button>
            <span>•</span>
            <span>{processedItems.filter((i) => i.priority === 'high').length} high priority</span>
            <span>•</span>
            <span>
              {processedItems.filter((i) => i.priority === 'medium').length} medium priority
            </span>
            <span>•</span>
            <span>{processedItems.filter((i) => i.priority === 'low').length} low priority</span>
          </div>

          {/* Items List */}
          {processedItems.map((item) => (
            <QueueItem
              key={item.id}
              item={item}
              isSelected={selectedIds.has(item.id)}
              onSelect={handleSelect}
              onAction={handleAction}
            />
          ))}
        </div>
      )}

      {/* Queue Stats */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Queue Statistics</CardTitle>
          <CardDescription>Summary of current work queue status</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-4">
            <div className="text-center p-4 rounded-lg bg-muted/50">
              <p className="text-2xl font-bold text-foreground">{items.length}</p>
              <p className="text-sm text-muted-foreground">Total Items</p>
            </div>
            <div className="text-center p-4 rounded-lg bg-danger-500/10">
              <p className="text-2xl font-bold text-danger-500">
                {items.filter((i) => i.priority === 'high').length}
              </p>
              <p className="text-sm text-muted-foreground">High Priority</p>
            </div>
            <div className="text-center p-4 rounded-lg bg-warning-500/10">
              <p className="text-2xl font-bold text-warning-500">
                {
                  items.filter((i) => {
                    const hours =
                      (Date.now() - new Date(i.created_at).getTime()) / (1000 * 60 * 60);
                    return hours > 24;
                  }).length
                }
              </p>
              <p className="text-sm text-muted-foreground">Over 24h</p>
            </div>
            <div className="text-center p-4 rounded-lg bg-success-500/10">
              <p className="text-2xl font-bold text-success-500">
                {items.length > 0
                  ? (items.reduce((sum, i) => sum + i.confidence, 0) / items.length).toFixed(1)
                  : 0}
                %
              </p>
              <p className="text-sm text-muted-foreground">Avg Confidence</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
