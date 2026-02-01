import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface PricingCardProps {
  name: string;
  description: string;
  price: number | null;
  annualPrice?: number;
  features: string[];
  popular?: boolean;
  highlighted?: boolean;
  ctaText?: string;
  isAnnual?: boolean;
}

export function PricingCard({
  name,
  description,
  price,
  annualPrice,
  features,
  popular,
  highlighted,
  ctaText = 'Get Started',
  isAnnual = false,
}: PricingCardProps) {
  const isPopular = popular || highlighted;
  const displayPrice = isAnnual && annualPrice ? annualPrice : price;
  const monthlyEquivalent = isAnnual && annualPrice ? Math.round(annualPrice / 12) : price;

  return (
    <Card className={`relative ${isPopular ? 'border-primary border-2 shadow-lg' : ''}`}>
      {isPopular && (
        <div className="absolute -top-4 left-1/2 -translate-x-1/2">
          <span className="bg-primary text-primary-foreground text-sm font-medium px-4 py-1 rounded-full">
            Most Popular
          </span>
        </div>
      )}
      <CardHeader className="text-center pb-2">
        <CardTitle className="text-2xl">{name}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="text-center">
        <div className="mt-4">
          {monthlyEquivalent !== null ? (
            <>
              <span className="text-4xl font-bold">${monthlyEquivalent}</span>
              <span className="text-muted-foreground">/month</span>
            </>
          ) : (
            <span className="text-4xl font-bold">Custom</span>
          )}
          {isAnnual && displayPrice !== null && (
            <p className="text-sm text-muted-foreground mt-1">
              Billed annually (${displayPrice}/year)
            </p>
          )}
        </div>
        <ul className="mt-8 space-y-3 text-left">
          {features.map((feature, idx) => (
            <li key={idx} className="flex items-start gap-3">
              <span className="text-green-500 mt-0.5">✓</span>
              <span className="text-sm">{feature}</span>
            </li>
          ))}
        </ul>
        <Button className="w-full mt-8" variant={isPopular ? 'default' : 'outline'}>
          {ctaText}
        </Button>
      </CardContent>
    </Card>
  );
}
