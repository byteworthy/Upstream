import type { ReactNode } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface Column<T> {
  key: keyof T | string;
  header: string;
  render?: (item: T) => ReactNode;
  hideOnMobile?: boolean;
  mobileLabel?: string;
}

interface ResponsiveTableProps<T> {
  data: T[];
  columns: Column<T>[];
  keyExtractor: (item: T) => string | number;
  onRowClick?: (item: T) => void;
  emptyMessage?: string;
  loading?: boolean;
}

function getCellValue<T>(item: T, column: Column<T>): ReactNode {
  if (column.render) {
    return column.render(item);
  }
  const key = column.key as keyof T;
  const value = item[key];
  if (value === null || value === undefined) {
    return '-';
  }
  return String(value);
}

export function ResponsiveTable<T>({
  data,
  columns,
  keyExtractor,
  onRowClick,
  emptyMessage = 'No data available',
  loading = false,
}: ResponsiveTableProps<T>) {
  // Columns visible on mobile (those not marked as hideOnMobile)
  const mobileColumns = columns.filter((col) => !col.hideOnMobile);

  if (loading) {
    return (
      <div className="space-y-4">
        {/* Desktop loading skeleton */}
        <div className="hidden md:block">
          <div className="rounded-lg border">
            <div className="h-12 bg-muted animate-pulse rounded-t-lg" />
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 border-t bg-muted/50 animate-pulse" />
            ))}
          </div>
        </div>
        {/* Mobile loading skeleton */}
        <div className="md:hidden space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 rounded-lg bg-muted animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-muted-foreground">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <>
      {/* Desktop Table View */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              {columns.map((col) => (
                <th
                  key={String(col.key)}
                  className="px-4 py-3 text-left text-sm font-medium text-muted-foreground"
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((item) => (
              <tr
                key={keyExtractor(item)}
                className={cn(
                  'border-b border-border transition-colors',
                  onRowClick && 'cursor-pointer hover:bg-muted/50'
                )}
                onClick={() => onRowClick?.(item)}
              >
                {columns.map((col) => (
                  <td key={String(col.key)} className="px-4 py-3 text-sm text-foreground">
                    {getCellValue(item, col)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile Card View */}
      <div className="md:hidden space-y-3">
        {data.map((item) => (
          <Card
            key={keyExtractor(item)}
            className={cn('transition-colors', onRowClick && 'cursor-pointer active:bg-muted/50')}
            onClick={() => onRowClick?.(item)}
          >
            <CardContent className="p-4">
              {/* First column as header */}
              {mobileColumns.length > 0 && (
                <div className="font-medium text-foreground mb-2">
                  {getCellValue(item, mobileColumns[0])}
                </div>
              )}

              {/* Other columns as key-value pairs */}
              <div className="space-y-1.5">
                {mobileColumns.slice(1).map((col) => (
                  <div key={String(col.key)} className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{col.mobileLabel || col.header}</span>
                    <span className="text-foreground font-medium">{getCellValue(item, col)}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
