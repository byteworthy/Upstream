import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

const FEATURES = [
  {
    title: 'Predictive Denial Prevention',
    description:
      'AI analyzes patterns to predict which claims are likely to be denied before submission, allowing proactive corrections.',
    icon: '🎯',
  },
  {
    title: 'Root Cause Analysis',
    description:
      'Automatically identify the underlying causes of denials with actionable insights to prevent future occurrences.',
    icon: '🔍',
  },
  {
    title: 'Real-time Scoring',
    description:
      'Every claim receives a confidence score indicating its likelihood of payment, enabling prioritization of review efforts.',
    icon: '📊',
  },
  {
    title: 'HIPAA Compliant',
    description:
      'Enterprise-grade security with AES-256 encryption, audit logging, and BAA included. SOC 2 certification in progress.',
    icon: '🔒',
  },
];

export function Features() {
  return (
    <section className="py-20 bg-background">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold sm:text-4xl">
            Why Healthcare Organizations Choose Upstream
          </h2>
          <p className="mt-4 text-lg text-muted-foreground max-w-2xl mx-auto">
            Our AI-powered platform helps revenue cycle teams work smarter, not harder.
          </p>
        </div>
        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((feature) => (
            <Card
              key={feature.title}
              className="border-2 hover:border-primary/50 transition-colors"
            >
              <CardHeader>
                <div className="text-4xl mb-4">{feature.icon}</div>
                <CardTitle>{feature.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-base">{feature.description}</CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
