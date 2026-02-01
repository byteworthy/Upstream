import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { ClaimScoreTable } from '@/components/scores/ClaimScoreTable';
import { ScoreFilters } from '@/components/scores/ScoreFilters';
import { claimScoresApi } from '@/lib/api';
import type { ClaimScore, ClaimScoreListParams } from '@/types/api';

type SortOrder = 'asc' | 'desc';

export function ClaimScores() {
  const [scores, setScores] = useState<ClaimScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [totalCount, setTotalCount] = useState(0);
  const [sortBy, setSortBy] = useState('scored_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [filters, setFilters] = useState<{
    tier?: 1 | 2 | 3;
    minConfidence?: number;
    maxConfidence?: number;
    startDate?: string;
    endDate?: string;
    search?: string;
  }>({});

  const fetchScores = useCallback(async () => {
    try {
      setLoading(true);
      const params: ClaimScoreListParams = {
        page,
        page_size: pageSize,
        ordering: sortOrder === 'desc' ? `-${sortBy}` : sortBy,
        automation_tier: filters.tier,
        min_confidence: filters.minConfidence,
        max_confidence: filters.maxConfidence,
        scored_after: filters.startDate,
        scored_before: filters.endDate,
      };
      const response = await claimScoresApi.list(params);
      setScores(response.results);
      setTotalCount(response.count);
    } catch {
      // Use mock data for development
      const mockScores: ClaimScore[] = Array.from({ length: pageSize }, (_, i) => ({
        id: page * pageSize - pageSize + i + 1,
        claim: 1000 + i,
        claim_id: `CLM-${(1000 + i).toString().padStart(6, '0')}`,
        overall_confidence: 50 + Math.random() * 50,
        coding_confidence: 60 + Math.random() * 40,
        eligibility_confidence: 70 + Math.random() * 30,
        medical_necessity_confidence: 55 + Math.random() * 45,
        documentation_confidence: 65 + Math.random() * 35,
        denial_risk_score: Math.random() * 30,
        fraud_risk_score: Math.random() * 10,
        compliance_risk_score: Math.random() * 20,
        automation_tier: ([1, 2, 3] as const)[Math.floor(Math.random() * 3)],
        recommended_action: ['auto_approve', 'queue_review', 'manual_review', 'escalate'][
          Math.floor(Math.random() * 4)
        ] as ClaimScore['recommended_action'],
        action_reasoning: 'Mock reasoning for the recommended action',
        feature_importance: { coding: 0.3, eligibility: 0.25, documentation: 0.25, necessity: 0.2 },
        model_version: '1.0.0',
        scored_at: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
        created_at: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
      }));
      setScores(mockScores);
      setTotalCount(150);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, sortBy, sortOrder, filters]);

  useEffect(() => {
    fetchScores();
  }, [fetchScores]);

  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('desc');
    }
  };

  const handleFilterChange = (newFilters: typeof filters) => {
    setFilters(newFilters);
    setPage(1);
  };

  const handleResetFilters = () => {
    setFilters({});
    setPage(1);
  };

  const totalPages = Math.ceil(totalCount / pageSize);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Claim Scores</h1>
        <p className="text-muted-foreground">View and filter scored claims</p>
      </div>

      {/* Filters */}
      <ScoreFilters
        filters={filters}
        onFilterChange={handleFilterChange}
        onReset={handleResetFilters}
      />

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">Loading scores...</div>
        </div>
      ) : (
        <ClaimScoreTable
          scores={scores}
          sortBy={sortBy}
          sortOrder={sortOrder}
          onSort={handleSort}
        />
      )}

      {/* Pagination */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>Show</span>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(1);
            }}
            className="rounded border border-border bg-background px-2 py-1"
          >
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
          <span>per page</span>
          <span className="mx-2">|</span>
          <span>
            Showing {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, totalCount)} of{' '}
            {totalCount}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page - 1)}
            disabled={page <= 1}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page + 1)}
            disabled={page >= totalPages}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
