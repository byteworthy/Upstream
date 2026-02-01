import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

type Tier = 'essentials' | 'professional' | 'enterprise';

interface TierSelectorProps {
  selectedTier?: Tier;
  onSelect: (tier: Tier) => void;
  onContinue: () => void;
  loading?: boolean;
}

const TIERS = [
  {
    id: 'essentials' as Tier,
    name: 'Essentials',
    price: 299,
    description: 'For small practices getting started',
    features: [
      'Up to 1,000 claims/month',
      'Basic analytics dashboard',
      'Email support',
      '1 user seat',
    ],
  },
  {
    id: 'professional' as Tier,
    name: 'Professional',
    price: 599,
    description: 'For growing organizations',
    features: [
      'Up to 10,000 claims/month',
      'Advanced analytics & reports',
      'Priority email support',
      '5 user seats',
      'API access',
    ],
    popular: true,
  },
  {
    id: 'enterprise' as Tier,
    name: 'Enterprise',
    price: 999,
    description: 'For large healthcare systems',
    features: [
      'Unlimited claims',
      'Custom analytics & reporting',
      'Dedicated support',
      'Unlimited user seats',
      'Full API access',
      'Custom integrations',
      'SLA guarantee',
    ],
  },
];

export function TierSelector({
  selectedTier,
  onSelect,
  onContinue,
  loading,
}: TierSelectorProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Choose Your Plan</CardTitle>
        <CardDescription>
          All plans include a 30-day free trial. No credit card required until trial ends.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 md:grid-cols-3 mb-6">
          {TIERS.map((tier) => (
            <div
              key={tier.id}
              onClick={() => onSelect(tier.id)}
              className={`relative cursor-pointer rounded-lg border-2 p-4 transition-all hover:shadow-md ${
                selectedTier === tier.id
                  ? 'border-primary bg-primary/5'
                  : 'border-muted hover:border-primary/50'
              }`}
            >
              {tier.popular && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-primary px-3 py-1 text-xs font-medium text-primary-foreground">
                  Most Popular
                </span>
              )}
              <h3 className="font-semibold text-lg">{tier.name}</h3>
              <p className="text-sm text-muted-foreground mt-1">{tier.description}</p>
              <p className="text-3xl font-bold mt-4">
                ${tier.price}
                <span className="text-sm font-normal text-muted-foreground">/mo</span>
              </p>
              <ul className="mt-4 space-y-2 text-sm">
                {tier.features.map((feature, idx) => (
                  <li key={idx} className="flex items-center gap-2">
                    <span className="text-green-500">✓</span>
                    {feature}
                  </li>
                ))}
              </ul>
              <div
                className={`mt-4 h-1 rounded-full transition-all ${
                  selectedTier === tier.id ? 'bg-primary' : 'bg-transparent'
                }`}
              />
            </div>
          ))}
        </div>
        <Button
          className="w-full"
          disabled={!selectedTier || loading}
          onClick={onContinue}
        >
          {loading ? 'Processing...' : 'Continue to Payment'}
        </Button>
      </CardContent>
    </Card>
  );
}
