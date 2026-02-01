const FEATURES = [
  {
    name: 'Claims per month',
    essentials: '1,000',
    professional: '10,000',
    enterprise: 'Unlimited',
  },
  { name: 'User seats', essentials: '1', professional: '5', enterprise: 'Unlimited' },
  {
    name: 'Analytics dashboard',
    essentials: 'Basic',
    professional: 'Advanced',
    enterprise: 'Custom',
  },
  { name: 'API access', essentials: '–', professional: '✓', enterprise: '✓' },
  { name: 'Custom integrations', essentials: '–', professional: '–', enterprise: '✓' },
  { name: 'Dedicated support', essentials: '–', professional: '–', enterprise: '✓' },
  { name: 'SLA guarantee', essentials: '–', professional: '99.9%', enterprise: '99.99%' },
  { name: 'Audit logging', essentials: '30 days', professional: '1 year', enterprise: '6 years' },
  { name: 'SSO/SAML', essentials: '–', professional: '–', enterprise: '✓' },
  {
    name: 'Onboarding',
    essentials: 'Self-serve',
    professional: 'Assisted',
    enterprise: 'Dedicated',
  },
];

export function FeatureComparison() {
  return (
    <div className="mt-16 overflow-x-auto">
      <table className="w-full min-w-[600px]">
        <thead>
          <tr className="border-b">
            <th className="text-left py-4 px-4 font-medium">Feature</th>
            <th className="text-center py-4 px-4 font-medium">Essentials</th>
            <th className="text-center py-4 px-4 font-medium">Professional</th>
            <th className="text-center py-4 px-4 font-medium">Enterprise</th>
          </tr>
        </thead>
        <tbody>
          {FEATURES.map((feature, idx) => (
            <tr key={feature.name} className={idx % 2 === 0 ? 'bg-muted/50' : ''}>
              <td className="py-4 px-4 text-sm">{feature.name}</td>
              <td className="py-4 px-4 text-center text-sm text-muted-foreground">
                {feature.essentials}
              </td>
              <td className="py-4 px-4 text-center text-sm text-muted-foreground">
                {feature.professional}
              </td>
              <td className="py-4 px-4 text-center text-sm text-muted-foreground">
                {feature.enterprise}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
