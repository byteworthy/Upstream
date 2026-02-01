import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface Invoice {
  id: string;
  date: string;
  amount: number;
  status: 'paid' | 'pending' | 'failed';
  pdfUrl?: string;
  description: string;
}

// Mock data - in production fetched from Stripe API
const mockInvoices: Invoice[] = [
  {
    id: 'inv_1',
    date: '2026-02-01',
    amount: 59900,
    status: 'paid',
    pdfUrl: '#',
    description: 'Professional Plan - February 2026',
  },
  {
    id: 'inv_2',
    date: '2026-01-01',
    amount: 59900,
    status: 'paid',
    pdfUrl: '#',
    description: 'Professional Plan - January 2026',
  },
  {
    id: 'inv_3',
    date: '2025-12-01',
    amount: 59900,
    status: 'paid',
    pdfUrl: '#',
    description: 'Professional Plan - December 2025',
  },
  {
    id: 'inv_4',
    date: '2025-11-01',
    amount: 59900,
    status: 'paid',
    pdfUrl: '#',
    description: 'Professional Plan - November 2025',
  },
  {
    id: 'inv_5',
    date: '2025-10-01',
    amount: 59900,
    status: 'paid',
    pdfUrl: '#',
    description: 'Professional Plan - October 2025',
  },
  {
    id: 'inv_6',
    date: '2025-09-01',
    amount: 29900,
    status: 'paid',
    pdfUrl: '#',
    description: 'Essentials Plan - September 2025',
  },
];

const STATUS_COLORS = {
  paid: 'bg-green-100 text-green-800',
  pending: 'bg-yellow-100 text-yellow-800',
  failed: 'bg-red-100 text-red-800',
};

const STATUS_LABELS = {
  paid: 'Paid',
  pending: 'Pending',
  failed: 'Failed',
};

export function InvoicesPage() {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [page, setPage] = useState(1);
  const perPage = 5;

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const formatAmount = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount / 100);
  };

  // Filter invoices by date range
  const filteredInvoices = mockInvoices.filter((invoice) => {
    if (startDate && new Date(invoice.date) < new Date(startDate)) return false;
    if (endDate && new Date(invoice.date) > new Date(endDate)) return false;
    return true;
  });

  // Paginate
  const totalPages = Math.ceil(filteredInvoices.length / perPage);
  const paginatedInvoices = filteredInvoices.slice((page - 1) * perPage, page * perPage);

  const downloadInvoice = (pdfUrl: string) => {
    // In production, this would trigger actual PDF download from Stripe
    window.open(pdfUrl, '_blank');
  };

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="mx-auto max-w-4xl space-y-8">
        <div>
          <h1 className="text-3xl font-bold">Invoice History</h1>
          <p className="text-muted-foreground">View and download your past invoices</p>
        </div>

        {/* Filters */}
        <Card>
          <CardHeader>
            <CardTitle>Filter by Date</CardTitle>
            <CardDescription>Select a date range to filter invoices</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4 items-end">
              <div className="flex-1">
                <label className="text-sm font-medium">Start Date</label>
                <Input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                />
              </div>
              <div className="flex-1">
                <label className="text-sm font-medium">End Date</label>
                <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
              </div>
              <Button
                variant="outline"
                onClick={() => {
                  setStartDate('');
                  setEndDate('');
                  setPage(1);
                }}
              >
                Clear
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Invoice List */}
        <Card>
          <CardHeader>
            <CardTitle>Invoices</CardTitle>
            <CardDescription>
              Showing {paginatedInvoices.length} of {filteredInvoices.length} invoices
            </CardDescription>
          </CardHeader>
          <CardContent>
            {paginatedInvoices.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">
                No invoices found for the selected date range
              </p>
            ) : (
              <div className="space-y-4">
                {paginatedInvoices.map((invoice) => (
                  <div
                    key={invoice.id}
                    className="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex-1">
                      <p className="font-medium">{invoice.description}</p>
                      <p className="text-sm text-muted-foreground">{formatDate(invoice.date)}</p>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-lg font-semibold">{formatAmount(invoice.amount)}</span>
                      <span
                        className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[invoice.status]}`}
                      >
                        {STATUS_LABELS[invoice.status]}
                      </span>
                      {invoice.pdfUrl && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => downloadInvoice(invoice.pdfUrl!)}
                        >
                          Download PDF
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex justify-center gap-2 mt-6">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Previous
                </Button>
                <span className="flex items-center px-4 text-sm text-muted-foreground">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default InvoicesPage;
