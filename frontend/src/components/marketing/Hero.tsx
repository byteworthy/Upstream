import { Button } from '@/components/ui/button';

export function Hero() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-background to-muted py-20 md:py-32">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl">
            <span className="block">Stop Revenue Leakage</span>
            <span className="block text-primary">Before It Happens</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
            Upstream uses AI to predict claim denials, identify root causes, and optimize your
            revenue cycle. Reduce denials by up to 35% and recover millions in lost revenue.
          </p>
          <div className="mt-10 flex justify-center gap-4">
            <Button size="lg" className="text-lg px-8">
              Start Free Trial
            </Button>
            <Button size="lg" variant="outline" className="text-lg px-8">
              Schedule Demo
            </Button>
          </div>
          <p className="mt-6 text-sm text-muted-foreground">
            30-day free trial. No credit card required.
          </p>
        </div>
      </div>
      {/* Background decoration */}
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute left-1/2 top-0 -translate-x-1/2 blur-3xl opacity-20">
          <div className="aspect-[1155/678] w-[72.1875rem] bg-gradient-to-tr from-primary to-secondary" />
        </div>
      </div>
    </section>
  );
}
