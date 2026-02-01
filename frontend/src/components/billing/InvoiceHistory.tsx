import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface Invoice {
  id: string;
  date: string;
  amount: number;
  status: 'paid' | 'pending' | 'failed';
  pdfUrl?: string;
}

interface InvoiceHistoryProps {
  invoices: Invoice[];
  onLoadMore?: () => void;
  hasMore?: boolean;
}

const STATUS_COLORS = {
  paid: 'text-green-500',
  pending: 'text-yellow-500',
  failed: 'text-red-500',
};

const STATUS_LABELS = {
  paid: 'Paid',
  pending: 'Pending',
  failed: 'Failed',
};

export function InvoiceHistory({ invoices, onLoadMore, hasMore }: InvoiceHistoryProps) {
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const formatAmount = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount / 100);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Invoice History</CardTitle>
        <CardDescription>Your past invoices and payment history</CardDescription>
      </CardHeader>
      <CardContent>
        {invoices.length === 0 ? (
          <p className="text-center text-muted-foreground py-4">No invoices yet</p>
        ) : (
          <div className="space-y-2">
            <div className="grid grid-cols-4 gap-4 text-sm font-medium text-muted-foreground border-b pb-2">
              <span>Date</span>
              <span>Amount</span>
              <span>Status</span>
              <span className="text-right">Actions</span>
            </div>
            {invoices.map((invoice) => (
              <div
                key={invoice.id}
                className="grid grid-cols-4 gap-4 text-sm py-2 border-b border-muted last:border-0"
              >
                <span>{formatDate(invoice.date)}</span>
                <span>{formatAmount(invoice.amount)}</span>
                <span className={STATUS_COLORS[invoice.status]}>
                  {STATUS_LABELS[invoice.status]}
                </span>
                <span className="text-right">
                  {invoice.pdfUrl && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => window.open(invoice.pdfUrl, '_blank')}
                    >
                      Download
                    </Button>
                  )}
                </span>
              </div>
            ))}
            {hasMore && onLoadMore && (
              <div className="pt-4 text-center">
                <Button variant="outline" onClick={onLoadMore}>
                  Load More
                </Button>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
