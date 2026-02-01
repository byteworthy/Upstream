import { useState } from 'react';
import { OnboardingProgress } from '@/components/onboarding/OnboardingProgress';
import { OrganizationSetup } from '@/components/onboarding/OrganizationSetup';
import { IntegrationSetup } from '@/components/onboarding/IntegrationSetup';
import { TeamInvites } from '@/components/onboarding/TeamInvites';
import { ComplianceAgreements } from '@/components/onboarding/ComplianceAgreements';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

const STEPS = [
  { title: 'Welcome', description: 'Get started' },
  { title: 'Organization', description: 'Your details' },
  { title: 'Integrations', description: 'Connect systems' },
  { title: 'Team', description: 'Invite members' },
  { title: 'Agreements', description: 'Review & accept' },
];

interface OnboardingData {
  // Organization
  organizationName: string;
  organizationType: string;
  npi: string;
  taxId: string;
  address: string;
  city: string;
  state: string;
  zipCode: string;
  // Integrations
  ehrSystem: string;
  clearinghouse: string;
  practiceManagement: string;
  dataFormat: string;
  // Team
  teamMembers: { email: string; role: 'admin' | 'analyst' | 'viewer' }[];
  // Compliance
  acceptedBaa: boolean;
  acceptedTerms: boolean;
  acceptedPrivacy: boolean;
}

const INITIAL_DATA: OnboardingData = {
  organizationName: '',
  organizationType: '',
  npi: '',
  taxId: '',
  address: '',
  city: '',
  state: '',
  zipCode: '',
  ehrSystem: '',
  clearinghouse: '',
  practiceManagement: '',
  dataFormat: '',
  teamMembers: [],
  acceptedBaa: false,
  acceptedTerms: false,
  acceptedPrivacy: false,
};

// Plan-based team member limits
const TEAM_LIMITS = {
  essentials: 1,
  professional: 5,
  enterprise: 999,
};

export function OnboardingPage() {
  const [currentStep, setCurrentStep] = useState(0);
  const [data, setData] = useState<OnboardingData>(INITIAL_DATA);
  const [isCompleted, setIsCompleted] = useState(false);

  // In production, this would come from the subscription
  const selectedPlan = 'professional';
  const maxTeamMembers = TEAM_LIMITS[selectedPlan as keyof typeof TEAM_LIMITS];

  const updateData = (updates: Partial<OnboardingData>) => {
    setData((prev) => ({ ...prev, ...updates }));
  };

  const handleComplete = async () => {
    // In production, this would submit to the API
    console.log('Onboarding data:', data);
    setIsCompleted(true);
  };

  if (isCompleted) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="max-w-lg w-full text-center">
          <CardHeader>
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg
                className="w-8 h-8 text-green-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <CardTitle className="text-2xl">You&apos;re All Set!</CardTitle>
            <CardDescription>
              Your account has been set up successfully. Welcome to Upstream Healthcare.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 bg-muted/50 rounded-lg text-left">
              <h4 className="font-medium mb-2">Quick Start Guide</h4>
              <ul className="text-sm text-muted-foreground space-y-2">
                <li className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-primary/20 text-primary text-xs flex items-center justify-center">
                    1
                  </span>
                  Upload your first batch of claims
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-primary/20 text-primary text-xs flex items-center justify-center">
                    2
                  </span>
                  Review AI-generated risk scores
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-primary/20 text-primary text-xs flex items-center justify-center">
                    3
                  </span>
                  Take action on flagged claims
                </li>
              </ul>
            </div>
            <div className="flex gap-3 justify-center">
              <Button variant="outline" onClick={() => (window.location.href = '/docs')}>
                View Documentation
              </Button>
              <Button onClick={() => (window.location.href = '/dashboard')}>Go to Dashboard</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <span className="text-xl font-bold">Upstream Healthcare</span>
          <span className="text-sm text-muted-foreground">
            Step {currentStep + 1} of {STEPS.length}
          </span>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8 max-w-2xl">
        <OnboardingProgress currentStep={currentStep} totalSteps={STEPS.length} steps={STEPS} />

        {/* Step 0: Welcome */}
        {currentStep === 0 && (
          <Card>
            <CardHeader className="text-center">
              <CardTitle className="text-2xl">Welcome to Upstream Healthcare</CardTitle>
              <CardDescription>
                Let&apos;s get your account set up. This will only take a few minutes.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid md:grid-cols-3 gap-4">
                <div className="p-4 rounded-lg border text-center">
                  <div className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-2">
                    <svg
                      className="w-5 h-5 text-primary"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
                      />
                    </svg>
                  </div>
                  <p className="text-sm font-medium">Organization</p>
                  <p className="text-xs text-muted-foreground">Tell us about your practice</p>
                </div>
                <div className="p-4 rounded-lg border text-center">
                  <div className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-2">
                    <svg
                      className="w-5 h-5 text-primary"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"
                      />
                    </svg>
                  </div>
                  <p className="text-sm font-medium">Integrations</p>
                  <p className="text-xs text-muted-foreground">Connect your systems</p>
                </div>
                <div className="p-4 rounded-lg border text-center">
                  <div className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-2">
                    <svg
                      className="w-5 h-5 text-primary"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z"
                      />
                    </svg>
                  </div>
                  <p className="text-sm font-medium">Team</p>
                  <p className="text-xs text-muted-foreground">Invite your colleagues</p>
                </div>
              </div>

              <div className="p-4 bg-muted/50 rounded-lg">
                <p className="text-sm">
                  <span className="font-medium">Your plan: </span>
                  <span className="capitalize">{selectedPlan}</span>
                  <span className="text-muted-foreground"> - 30 day free trial</span>
                </p>
              </div>

              <Button className="w-full" size="lg" onClick={() => setCurrentStep(1)}>
                Get Started
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Step 1: Organization */}
        {currentStep === 1 && (
          <OrganizationSetup
            data={{
              organizationName: data.organizationName,
              organizationType: data.organizationType,
              npi: data.npi,
              taxId: data.taxId,
              address: data.address,
              city: data.city,
              state: data.state,
              zipCode: data.zipCode,
            }}
            onUpdate={updateData}
            onNext={() => setCurrentStep(2)}
            onBack={() => setCurrentStep(0)}
          />
        )}

        {/* Step 2: Integrations */}
        {currentStep === 2 && (
          <IntegrationSetup
            data={{
              ehrSystem: data.ehrSystem,
              clearinghouse: data.clearinghouse,
              practiceManagement: data.practiceManagement,
              dataFormat: data.dataFormat,
            }}
            onUpdate={updateData}
            onNext={() => setCurrentStep(3)}
            onBack={() => setCurrentStep(1)}
          />
        )}

        {/* Step 3: Team */}
        {currentStep === 3 && (
          <TeamInvites
            members={data.teamMembers}
            onUpdate={(members) => updateData({ teamMembers: members })}
            onNext={() => setCurrentStep(4)}
            onBack={() => setCurrentStep(2)}
            maxMembers={maxTeamMembers}
          />
        )}

        {/* Step 4: Compliance */}
        {currentStep === 4 && (
          <ComplianceAgreements
            data={{
              acceptedBaa: data.acceptedBaa,
              acceptedTerms: data.acceptedTerms,
              acceptedPrivacy: data.acceptedPrivacy,
            }}
            onUpdate={updateData}
            onComplete={handleComplete}
            onBack={() => setCurrentStep(3)}
          />
        )}
      </div>
    </div>
  );
}

export default OnboardingPage;
