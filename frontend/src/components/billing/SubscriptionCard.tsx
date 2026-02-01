import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface SubscriptionCardProps {
  tier: 'essentials' | 'professional' | 'enterprise';
  status: 'trialing' | 'active' | 'past_due' | 'canceled';
  currentPeriodEnd?: string;
  trialEnd?: string;
  cancelAtPeriodEnd?: boolean;
  onManage?: () => void;
  onCancel?: () => void;
}

const TIER_PRICING = {
  essentials: 299,
  professional: 599,
  enterprise: 999,
};

const TIER_NAMES = {
  essentials: 'Essentials',
  professional: 'Professional',
  enterprise: 'Enterprise',
};

const STATUS_COLORS = {
  trialing: 'text-blue-500',
  active: 'text-green-500',
  past_due: 'text-yellow-500',
  canceled: 'text-red-500',
};

const STATUS_LABELS = {
  trialing: 'Trial',
  active: 'Active',
  past_due: 'Past Due',
  canceled: 'Canceled',
};

export function SubscriptionCard({
  tier,
  status,
  currentPeriodEnd,
  trialEnd,
  cancelAtPeriodEnd,
  onManage,
  onCancel,
}: SubscriptionCardProps) {
  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>{TIER_NAMES[tier]} Plan</CardTitle>
            <CardDescription>
              <span className={STATUS_COLORS[status]}>{STATUS_LABELS[status]}</span>
              {cancelAtPeriodEnd && (
                <span className="ml-2 text-yellow-500">(Canceling at period end)</span>
              )}
            </CardDescription>
          </div>
          <div className="text-right">
            <p className="text-3xl font-bold">${TIER_PRICING[tier]}</p>
            <p className="text-sm text-muted-foreground">/month</p>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="grid gap-2 text-sm">
            {status === 'trialing' && trialEnd && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Trial ends</span>
                <span>{formatDate(trialEnd)}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-muted-foreground">Next billing date</span>
              <span>{formatDate(currentPeriodEnd)}</span>
            </div>
          </div>

          <div className="flex gap-2">
            {onManage && (
              <Button onClick={onManage} className="flex-1">
                Manage Subscription
              </Button>
            )}
            {onCancel && status !== 'canceled' && !cancelAtPeriodEnd && (
              <Button
                variant="outline"
                onClick={onCancel}
                className="text-red-500 hover:text-red-600"
              >
                Cancel
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
