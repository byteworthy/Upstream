import { Button } from '@/components/ui/button';
import { PricingCard } from '@/components/marketing/PricingCard';
import { FeatureComparison } from '@/components/marketing/FeatureComparison';

const PRICING_TIERS = [
  {
    name: 'Essentials',
    price: 299,
    description: 'For small practices getting started with claims intelligence',
    features: [
      '1,000 claims per month',
      '1 user seat',
      'Basic analytics dashboard',
      '30-day audit logging',
      'Self-serve onboarding',
      'Email support',
    ],
    highlighted: false,
    ctaText: 'Start Free Trial',
  },
  {
    name: 'Professional',
    price: 599,
    description: 'For growing organizations that need advanced insights',
    features: [
      '10,000 claims per month',
      '5 user seats',
      'Advanced analytics dashboard',
      'API access',
      '99.9% SLA guarantee',
      '1-year audit logging',
      'Assisted onboarding',
      'Priority support',
    ],
    highlighted: true,
    ctaText: 'Start Free Trial',
  },
  {
    name: 'Enterprise',
    price: null,
    description: 'For large health systems with custom requirements',
    features: [
      'Unlimited claims',
      'Unlimited user seats',
      'Custom analytics & reporting',
      'API access with higher limits',
      'Custom integrations',
      'Dedicated support',
      '99.99% SLA guarantee',
      '6-year audit logging',
      'SSO/SAML authentication',
      'Dedicated onboarding',
    ],
    highlighted: false,
    ctaText: 'Contact Sales',
  },
];

export function PricingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <a href="/" className="text-xl font-bold">
            Upstream Healthcare
          </a>
          <nav className="hidden md:flex gap-6">
            <a href="/features" className="text-muted-foreground hover:text-foreground">
              Features
            </a>
            <a href="/pricing" className="text-foreground font-medium">
              Pricing
            </a>
            <a href="/case-studies" className="text-muted-foreground hover:text-foreground">
              Case Studies
            </a>
            <a href="/security" className="text-muted-foreground hover:text-foreground">
              Security
            </a>
          </nav>
          <div className="flex gap-2">
            <Button variant="ghost">Sign In</Button>
            <Button>Start Free Trial</Button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="py-16 text-center">
        <div className="container mx-auto px-4">
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl mb-4">
            Simple, Transparent Pricing
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Choose the plan that fits your organization. All plans include a 30-day free trial with
            no credit card required.
          </p>
        </div>
      </section>

      {/* Pricing Cards */}
      <section className="pb-16">
        <div className="container mx-auto px-4">
          <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
            {PRICING_TIERS.map((tier) => (
              <PricingCard
                key={tier.name}
                name={tier.name}
                price={tier.price}
                description={tier.description}
                features={tier.features}
                highlighted={tier.highlighted}
                ctaText={tier.ctaText}
              />
            ))}
          </div>
        </div>
      </section>

      {/* Feature Comparison */}
      <section className="py-16 bg-muted/30">
        <div className="container mx-auto px-4">
          <h2 className="text-3xl font-bold text-center mb-4">Compare Plans</h2>
          <p className="text-muted-foreground text-center mb-8 max-w-2xl mx-auto">
            See exactly what&apos;s included in each plan to find the right fit for your
            organization.
          </p>
          <div className="max-w-4xl mx-auto">
            <FeatureComparison />
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-16">
        <div className="container mx-auto px-4 max-w-3xl">
          <h2 className="text-3xl font-bold text-center mb-12">Frequently Asked Questions</h2>
          <div className="space-y-8">
            <div>
              <h3 className="text-lg font-semibold mb-2">What happens after my free trial?</h3>
              <p className="text-muted-foreground">
                After your 30-day trial, you&apos;ll be automatically enrolled in your selected
                plan. You can cancel anytime before the trial ends without being charged.
              </p>
            </div>
            <div>
              <h3 className="text-lg font-semibold mb-2">Can I change plans later?</h3>
              <p className="text-muted-foreground">
                Yes, you can upgrade or downgrade your plan at any time. Changes take effect at the
                start of your next billing cycle.
              </p>
            </div>
            <div>
              <h3 className="text-lg font-semibold mb-2">What counts as a &quot;claim&quot;?</h3>
              <p className="text-muted-foreground">
                A claim is any medical claim processed through our system for analysis. This
                includes initial submissions and resubmissions.
              </p>
            </div>
            <div>
              <h3 className="text-lg font-semibold mb-2">Do you offer HIPAA BAAs?</h3>
              <p className="text-muted-foreground">
                Yes, we provide Business Associate Agreements (BAAs) for all customers. Enterprise
                customers can also request custom BAA terms.
              </p>
            </div>
            <div>
              <h3 className="text-lg font-semibold mb-2">What payment methods do you accept?</h3>
              <p className="text-muted-foreground">
                We accept all major credit cards. Enterprise customers can also pay via ACH or wire
                transfer with annual billing.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-16 bg-primary text-primary-foreground">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to Stop Revenue Leakage?</h2>
          <p className="text-xl opacity-90 mb-8 max-w-2xl mx-auto">
            Start your free trial today and see how Upstream can help your organization recover lost
            revenue.
          </p>
          <Button size="lg" variant="secondary">
            Start Your Free Trial
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-12">
        <div className="container mx-auto px-4">
          <div className="grid md:grid-cols-4 gap-8">
            <div>
              <h4 className="font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <a href="/features">Features</a>
                </li>
                <li>
                  <a href="/pricing">Pricing</a>
                </li>
                <li>
                  <a href="/integrations">Integrations</a>
                </li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Company</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <a href="/about">About</a>
                </li>
                <li>
                  <a href="/case-studies">Case Studies</a>
                </li>
                <li>
                  <a href="/careers">Careers</a>
                </li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Resources</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <a href="/docs">Documentation</a>
                </li>
                <li>
                  <a href="/blog">Blog</a>
                </li>
                <li>
                  <a href="/support">Support</a>
                </li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Legal</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <a href="/privacy">Privacy Policy</a>
                </li>
                <li>
                  <a href="/terms">Terms of Service</a>
                </li>
                <li>
                  <a href="/security">Security</a>
                </li>
              </ul>
            </div>
          </div>
          <div className="border-t mt-8 pt-8 text-center text-sm text-muted-foreground">
            <p>&copy; 2026 Upstream Healthcare, Inc. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default PricingPage;
