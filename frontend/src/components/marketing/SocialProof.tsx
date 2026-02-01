const LOGOS = [
  'Healthcare System A',
  'Regional Medical Center',
  'Community Health Network',
  'University Hospital',
  'Specialty Care Group',
];

const TESTIMONIALS = [
  {
    quote:
      'Upstream reduced our denial rate by 32% in the first quarter. The ROI was immediate and substantial.',
    author: 'Sarah Chen',
    title: 'Director of Revenue Cycle',
    company: 'Regional Medical Center',
  },
  {
    quote:
      'The predictive scoring has transformed how we prioritize claims. We catch issues before they become denials.',
    author: 'Michael Rodriguez',
    title: 'VP of Finance',
    company: 'Community Health Network',
  },
];

export function SocialProof() {
  return (
    <section className="py-20 bg-muted">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Logo cloud */}
        <div className="text-center mb-16">
          <p className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
            Trusted by leading healthcare organizations
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-8">
            {LOGOS.map((logo) => (
              <div
                key={logo}
                className="px-6 py-3 bg-background rounded-lg text-muted-foreground font-medium"
              >
                {logo}
              </div>
            ))}
          </div>
        </div>

        {/* Testimonials */}
        <div className="grid gap-8 md:grid-cols-2 max-w-4xl mx-auto">
          {TESTIMONIALS.map((testimonial) => (
            <div key={testimonial.author} className="bg-background rounded-lg p-8 shadow-sm">
              <blockquote className="text-lg italic text-foreground">
                "{testimonial.quote}"
              </blockquote>
              <div className="mt-6">
                <p className="font-semibold">{testimonial.author}</p>
                <p className="text-sm text-muted-foreground">
                  {testimonial.title}, {testimonial.company}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Stats */}
        <div className="mt-16 grid gap-8 md:grid-cols-3 text-center">
          <div>
            <p className="text-4xl font-bold text-primary">35%</p>
            <p className="mt-2 text-muted-foreground">Average denial reduction</p>
          </div>
          <div>
            <p className="text-4xl font-bold text-primary">$2.4M</p>
            <p className="mt-2 text-muted-foreground">Average annual savings</p>
          </div>
          <div>
            <p className="text-4xl font-bold text-primary">98%</p>
            <p className="mt-2 text-muted-foreground">Customer satisfaction</p>
          </div>
        </div>
      </div>
    </section>
  );
}
