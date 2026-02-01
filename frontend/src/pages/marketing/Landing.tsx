import { Hero } from '@/components/marketing/Hero';
import { Features } from '@/components/marketing/Features';
import { SocialProof } from '@/components/marketing/SocialProof';
import { Button } from '@/components/ui/button';

export function LandingPage() {
  return (
    <div className="min-h-screen">
      {/* Navigation */}
      <nav className="fixed top-0 w-full bg-background/80 backdrop-blur-sm z-50 border-b">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center">
              <span className="text-xl font-bold text-primary">Upstream</span>
            </div>
            <div className="hidden md:flex items-center gap-8">
              <a href="/pricing" className="text-sm font-medium hover:text-primary">
                Pricing
              </a>
              <a href="/case-studies" className="text-sm font-medium hover:text-primary">
                Case Studies
              </a>
              <a href="/docs" className="text-sm font-medium hover:text-primary">
                Documentation
              </a>
              <Button variant="outline" size="sm">
                Sign In
              </Button>
              <Button size="sm">Start Free Trial</Button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="pt-16">
        <Hero />
        <Features />
        <SocialProof />

        {/* Final CTA */}
        <section className="py-20 bg-primary text-primary-foreground">
          <div className="mx-auto max-w-4xl px-4 text-center">
            <h2 className="text-3xl font-bold sm:text-4xl">
              Ready to transform your revenue cycle?
            </h2>
            <p className="mt-4 text-lg opacity-90">
              Join hundreds of healthcare organizations already using Upstream to prevent denials
              and maximize revenue.
            </p>
            <div className="mt-10 flex justify-center gap-4">
              <Button size="lg" variant="secondary" className="text-lg px-8">
                Start Free Trial
              </Button>
              <Button
                size="lg"
                variant="outline"
                className="text-lg px-8 border-primary-foreground text-primary-foreground hover:bg-primary-foreground hover:text-primary"
              >
                Talk to Sales
              </Button>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-muted py-12">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid gap-8 md:grid-cols-4">
            <div>
              <span className="text-lg font-bold text-primary">Upstream</span>
              <p className="mt-4 text-sm text-muted-foreground">
                AI-powered claims intelligence for healthcare.
              </p>
            </div>
            <div>
              <h3 className="font-semibold mb-4">Product</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <a href="/pricing" className="hover:text-foreground">
                    Pricing
                  </a>
                </li>
                <li>
                  <a href="/features" className="hover:text-foreground">
                    Features
                  </a>
                </li>
                <li>
                  <a href="/integrations" className="hover:text-foreground">
                    Integrations
                  </a>
                </li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold mb-4">Resources</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <a href="/docs" className="hover:text-foreground">
                    Documentation
                  </a>
                </li>
                <li>
                  <a href="/case-studies" className="hover:text-foreground">
                    Case Studies
                  </a>
                </li>
                <li>
                  <a href="/blog" className="hover:text-foreground">
                    Blog
                  </a>
                </li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold mb-4">Company</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <a href="/about" className="hover:text-foreground">
                    About
                  </a>
                </li>
                <li>
                  <a href="/security" className="hover:text-foreground">
                    Security
                  </a>
                </li>
                <li>
                  <a href="/contact" className="hover:text-foreground">
                    Contact
                  </a>
                </li>
              </ul>
            </div>
          </div>
          <div className="mt-12 pt-8 border-t text-center text-sm text-muted-foreground">
            <p>&copy; 2026 Upstream Healthcare, Inc. All rights reserved.</p>
            <div className="mt-4 space-x-4">
              <a href="/privacy" className="hover:text-foreground">
                Privacy Policy
              </a>
              <a href="/terms" className="hover:text-foreground">
                Terms of Service
              </a>
              <a href="/hipaa" className="hover:text-foreground">
                HIPAA Compliance
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default LandingPage;
