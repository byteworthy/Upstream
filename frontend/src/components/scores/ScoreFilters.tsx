import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Search, X } from 'lucide-react';

interface ScoreFiltersProps {
  filters: {
    tier?: 1 | 2 | 3;
    minConfidence?: number;
    maxConfidence?: number;
    startDate?: string;
    endDate?: string;
    search?: string;
  };
  onFilterChange: (filters: ScoreFiltersProps['filters']) => void;
  onReset: () => void;
}

export function ScoreFilters({ filters, onFilterChange, onReset }: ScoreFiltersProps) {
  const hasFilters = Object.values(filters).some((v) => v !== undefined && v !== '');

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-4">
      {/* Search */}
      <div className="relative flex-1 min-w-[200px]">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search claim ID..."
          value={filters.search || ''}
          onChange={(e) => onFilterChange({ ...filters, search: e.target.value })}
          className="pl-9"
        />
      </div>

      {/* Tier Filter */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Tier:</span>
        <div className="flex gap-1">
          {[1, 2, 3].map((tier) => (
            <Button
              key={tier}
              variant={filters.tier === tier ? 'default' : 'outline'}
              size="sm"
              onClick={() =>
                onFilterChange({
                  ...filters,
                  tier: filters.tier === tier ? undefined : (tier as 1 | 2 | 3),
                })
              }
            >
              {tier}
            </Button>
          ))}
        </div>
      </div>

      {/* Confidence Range */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Confidence:</span>
        <Input
          type="number"
          placeholder="Min"
          min={0}
          max={100}
          value={filters.minConfidence || ''}
          onChange={(e) =>
            onFilterChange({
              ...filters,
              minConfidence: e.target.value ? Number(e.target.value) : undefined,
            })
          }
          className="w-20"
        />
        <span className="text-muted-foreground">-</span>
        <Input
          type="number"
          placeholder="Max"
          min={0}
          max={100}
          value={filters.maxConfidence || ''}
          onChange={(e) =>
            onFilterChange({
              ...filters,
              maxConfidence: e.target.value ? Number(e.target.value) : undefined,
            })
          }
          className="w-20"
        />
      </div>

      {/* Date Range */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Date:</span>
        <Input
          type="date"
          value={filters.startDate || ''}
          onChange={(e) => onFilterChange({ ...filters, startDate: e.target.value })}
          className="w-36"
        />
        <span className="text-muted-foreground">-</span>
        <Input
          type="date"
          value={filters.endDate || ''}
          onChange={(e) => onFilterChange({ ...filters, endDate: e.target.value })}
          className="w-36"
        />
      </div>

      {/* Reset */}
      {hasFilters && (
        <Button variant="ghost" size="sm" onClick={onReset}>
          <X className="mr-1 h-4 w-4" />
          Clear
        </Button>
      )}
    </div>
  );
}
