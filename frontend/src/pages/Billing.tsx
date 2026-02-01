import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { SubscriptionCard } from '@/components/billing/SubscriptionCard';
import { InvoiceHistory } from '@/components/billing/InvoiceHistory';

// Mock data - in production this would come from API
const mockSubscription = {
  tier: 'professional' as const,
  status: 'active' as const,
  currentPeriodEnd: '2026-03-01T00:00:00Z',
  trialEnd: null,
  cancelAtPeriodEnd: false,
};

const mockInvoices = [
  { id: 'inv_1', date: '2026-02-01', amount: 59900, status: 'paid' as const, pdfUrl: '#' },
  { id: 'inv_2', date: '2026-01-01', amount: 59900, status: 'paid' as const, pdfUrl: '#' },
  { id: 'inv_3', date: '2025-12-01', amount: 59900, status: 'paid' as const, pdfUrl: '#' },
];

const TIER_FEATURES = {
  essentials: [
    'Up to 1,000 claims/month',
    'Basic analytics dashboard',
    'Email support',
    '1 user seat',
  ],
  professional: [
    'Up to 10,000 claims/month',
    'Advanced analytics & reports',
    'Priority email support',
    '5 user seats',
    'API access',
  ],
  enterprise: [
    'Unlimited claims',
    'Custom analytics & reporting',
    'Dedicated support',
    'Unlimited user seats',
    'Full API access',
    'Custom integrations',
    'SLA guarantee',
  ],
};

export function BillingPage() {
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  const handleManageSubscription = () => {
    // In production, this would redirect to Stripe billing portal
    console.log('Redirecting to Stripe billing portal...');
    // window.location.href = '/api/billing/portal';
  };

  const handleCancelSubscription = () => {
    setShowCancelConfirm(true);
  };

  const confirmCancel = () => {
    // In production, this would call API to cancel subscription
    console.log('Canceling subscription...');
    setShowCancelConfirm(false);
  };

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="mx-auto max-w-4xl space-y-8">
        <div>
          <h1 className="text-3xl font-bold">Billing & Subscription</h1>
          <p className="text-muted-foreground">Manage your subscription and billing details</p>
        </div>

        {/* Current Subscription */}
        <SubscriptionCard
          tier={mockSubscription.tier}
          status={mockSubscription.status}
          currentPeriodEnd={mockSubscription.currentPeriodEnd}
          cancelAtPeriodEnd={mockSubscription.cancelAtPeriodEnd}
          onManage={handleManageSubscription}
          onCancel={handleCancelSubscription}
        />

        {/* Cancel Confirmation Modal */}
        {showCancelConfirm && (
          <Card className="border-red-200 bg-red-50 dark:bg-red-950 dark:border-red-800">
            <CardHeader>
              <CardTitle className="text-red-600">Cancel Subscription?</CardTitle>
              <CardDescription>
                Your subscription will remain active until the end of the current billing period.
                You will lose access to premium features after that date.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex gap-2">
              <Button variant="destructive" onClick={confirmCancel}>
                Yes, Cancel Subscription
              </Button>
              <Button variant="outline" onClick={() => setShowCancelConfirm(false)}>
                Keep Subscription
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Plan Comparison */}
        <Card>
          <CardHeader>
            <CardTitle>Available Plans</CardTitle>
            <CardDescription>Upgrade or downgrade your plan at any time</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-3">
              {(['essentials', 'professional', 'enterprise'] as const).map((tier) => (
                <div
                  key={tier}
                  className={`rounded-lg border p-4 ${
                    tier === mockSubscription.tier ? 'border-primary bg-primary/5' : 'border-muted'
                  }`}
                >
                  <h3 className="font-semibold capitalize">{tier}</h3>
                  <p className="text-2xl font-bold mt-2">
                    ${tier === 'essentials' ? 299 : tier === 'professional' ? 599 : 999}
                    <span className="text-sm font-normal text-muted-foreground">/mo</span>
                  </p>
                  <ul className="mt-4 space-y-2 text-sm">
                    {TIER_FEATURES[tier].map((feature, idx) => (
                      <li key={idx} className="flex items-center gap-2">
                        <span className="text-green-500">✓</span>
                        {feature}
                      </li>
                    ))}
                  </ul>
                  <Button
                    className="w-full mt-4"
                    variant={tier === mockSubscription.tier ? 'secondary' : 'default'}
                    disabled={tier === mockSubscription.tier}
                  >
                    {tier === mockSubscription.tier
                      ? 'Current Plan'
                      : tier === 'enterprise'
                        ? 'Contact Sales'
                        : 'Switch Plan'}
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Invoice History */}
        <InvoiceHistory invoices={mockInvoices} hasMore={false} />
      </div>
    </div>
  );
}

export default BillingPage;
