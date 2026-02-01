import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

interface CaseStudyData {
  company: string;
  logo?: string;
  industry: string;
  size: string;
  location: string;
  challenge: string;
  solution: string;
  results: {
    metric: string;
    value: string;
    description: string;
  }[];
  quote: {
    text: string;
    author: string;
    title: string;
  };
  timeline: string;
}

// Example case study data - in production, this would come from CMS or API
const SAMPLE_CASE_STUDY: CaseStudyData = {
  company: 'Midwest Regional Health System',
  industry: 'Healthcare Provider',
  size: '5,000+ employees',
  location: 'Chicago, IL',
  challenge: `Midwest Regional Health System was struggling with a denial rate of 12%, significantly above the industry average. Their revenue cycle team was overwhelmed with manual reviews, leading to delayed appeals and missed deadlines. The organization estimated they were losing over $4.2 million annually due to preventable denials.

Key challenges included:
- Inability to identify denial patterns before submission
- Manual review processes taking 3-5 days per claim
- Lack of real-time visibility into claim status
- Inconsistent coding practices across departments`,
  solution: `Midwest Regional implemented Upstream Healthcare's claims intelligence platform across their entire revenue cycle operation. The implementation included:

1. **AI-Powered Pre-Submission Review**: Every claim is automatically analyzed for denial risk before submission, with specific recommendations for improvement.

2. **Real-Time Dashboard**: Revenue cycle managers gained instant visibility into claim status, denial trends, and team performance.

3. **Automated Workflows**: High-risk claims are automatically flagged and routed to specialized reviewers.

4. **Integration with Existing EHR**: Seamless connection with their Epic system meant no disruption to existing workflows.`,
  results: [
    {
      metric: 'Denial Rate Reduction',
      value: '47%',
      description: 'Denial rate dropped from 12% to 6.4% within 6 months',
    },
    {
      metric: 'Revenue Recovered',
      value: '$2.1M',
      description: 'Additional annual revenue from prevented denials',
    },
    {
      metric: 'Time Savings',
      value: '60%',
      description: 'Reduction in manual review time per claim',
    },
    {
      metric: 'ROI',
      value: '340%',
      description: 'Return on investment in the first year',
    },
  ],
  quote: {
    text: "Upstream has transformed how we approach claims management. What used to take our team days now happens automatically, and we're catching issues before they become costly denials. The ROI was evident within the first quarter.",
    author: 'Sarah Chen',
    title: 'VP of Revenue Cycle, Midwest Regional Health System',
  },
  timeline: '6 months from implementation to full results',
};

interface CaseStudyTemplateProps {
  data?: CaseStudyData;
}

export function CaseStudyTemplate({ data = SAMPLE_CASE_STUDY }: CaseStudyTemplateProps) {
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
            <a href="/pricing" className="text-muted-foreground hover:text-foreground">
              Pricing
            </a>
            <a href="/case-studies" className="text-foreground font-medium">
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

      {/* Breadcrumb */}
      <div className="border-b bg-muted/30">
        <div className="container mx-auto px-4 py-3">
          <nav className="text-sm text-muted-foreground">
            <a href="/" className="hover:text-foreground">
              Home
            </a>
            <span className="mx-2">/</span>
            <a href="/case-studies" className="hover:text-foreground">
              Case Studies
            </a>
            <span className="mx-2">/</span>
            <span className="text-foreground">{data.company}</span>
          </nav>
        </div>
      </div>

      {/* Hero */}
      <section className="py-16 bg-gradient-to-b from-muted/50 to-background">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto text-center">
            <p className="text-sm font-medium text-primary mb-4">CASE STUDY</p>
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl mb-6">{data.company}</h1>
            <p className="text-xl text-muted-foreground mb-8">
              How {data.company} reduced denials by 47% and recovered $2.1M in annual revenue
            </p>
            <div className="flex justify-center gap-8 text-sm text-muted-foreground">
              <div>
                <span className="font-medium text-foreground">Industry:</span> {data.industry}
              </div>
              <div>
                <span className="font-medium text-foreground">Size:</span> {data.size}
              </div>
              <div>
                <span className="font-medium text-foreground">Location:</span> {data.location}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Results Highlight */}
      <section className="py-12 border-b">
        <div className="container mx-auto px-4">
          <div className="grid md:grid-cols-4 gap-8 max-w-4xl mx-auto">
            {data.results.map((result) => (
              <div key={result.metric} className="text-center">
                <p className="text-4xl font-bold text-primary mb-2">{result.value}</p>
                <p className="font-medium mb-1">{result.metric}</p>
                <p className="text-sm text-muted-foreground">{result.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Main Content */}
      <section className="py-16">
        <div className="container mx-auto px-4">
          <div className="max-w-3xl mx-auto">
            {/* Challenge */}
            <div className="mb-12">
              <h2 className="text-2xl font-bold mb-4">The Challenge</h2>
              <div className="prose prose-gray max-w-none">
                {data.challenge.split('\n\n').map((paragraph, idx) => (
                  <p key={idx} className="text-muted-foreground mb-4 whitespace-pre-line">
                    {paragraph}
                  </p>
                ))}
              </div>
            </div>

            {/* Quote */}
            <Card className="my-12 bg-primary/5 border-primary/20">
              <CardContent className="p-8">
                <blockquote className="text-lg italic mb-4">
                  &ldquo;{data.quote.text}&rdquo;
                </blockquote>
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center">
                    <span className="text-lg font-semibold">
                      {data.quote.author
                        .split(' ')
                        .map((n) => n[0])
                        .join('')}
                    </span>
                  </div>
                  <div>
                    <p className="font-semibold">{data.quote.author}</p>
                    <p className="text-sm text-muted-foreground">{data.quote.title}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Solution */}
            <div className="mb-12">
              <h2 className="text-2xl font-bold mb-4">The Solution</h2>
              <div className="prose prose-gray max-w-none">
                {data.solution.split('\n\n').map((paragraph, idx) => (
                  <p key={idx} className="text-muted-foreground mb-4 whitespace-pre-line">
                    {paragraph}
                  </p>
                ))}
              </div>
            </div>

            {/* Results */}
            <div className="mb-12">
              <h2 className="text-2xl font-bold mb-4">The Results</h2>
              <p className="text-muted-foreground mb-6">
                Within {data.timeline}, {data.company} achieved measurable improvements across all
                key metrics:
              </p>
              <div className="grid sm:grid-cols-2 gap-4">
                {data.results.map((result) => (
                  <Card key={result.metric}>
                    <CardContent className="p-6">
                      <p className="text-3xl font-bold text-primary mb-2">{result.value}</p>
                      <p className="font-medium">{result.metric}</p>
                      <p className="text-sm text-muted-foreground mt-1">{result.description}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-16 bg-muted/50">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to Achieve Similar Results?</h2>
          <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
            See how Upstream can help your organization reduce denials and recover revenue.
          </p>
          <div className="flex justify-center gap-4">
            <Button size="lg">Start Your Free Trial</Button>
            <Button size="lg" variant="outline">
              Request a Demo
            </Button>
          </div>
        </div>
      </section>

      {/* Related Case Studies */}
      <section className="py-16">
        <div className="container mx-auto px-4">
          <h2 className="text-2xl font-bold text-center mb-8">More Success Stories</h2>
          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {[
              {
                company: 'Coastal Medical Group',
                result: '52% denial reduction',
                industry: 'Multi-specialty Practice',
              },
              {
                company: 'Summit Health Partners',
                result: '$3.4M revenue recovered',
                industry: 'Hospital System',
              },
              {
                company: 'Valley Orthopedics',
                result: '70% faster processing',
                industry: 'Specialty Practice',
              },
            ].map((study) => (
              <Card
                key={study.company}
                className="hover:shadow-md transition-shadow cursor-pointer"
              >
                <CardContent className="p-6">
                  <p className="font-semibold mb-1">{study.company}</p>
                  <p className="text-sm text-muted-foreground mb-4">{study.industry}</p>
                  <p className="text-lg font-bold text-primary">{study.result}</p>
                  <a href="#" className="text-sm text-primary hover:underline mt-4 inline-block">
                    Read case study &rarr;
                  </a>
                </CardContent>
              </Card>
            ))}
          </div>
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

export default CaseStudyTemplate;
