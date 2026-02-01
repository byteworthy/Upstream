import { useState } from 'react';
import { AccountForm } from '@/components/signup/AccountForm';
import { TierSelector } from '@/components/signup/TierSelector';

type Step = 'account' | 'tier' | 'checkout' | 'success';
type Tier = 'essentials' | 'professional' | 'enterprise';

interface AccountData {
  email: string;
  password: string;
  confirmPassword: string;
  companyName: string;
}

export function SignupPage() {
  const [step, setStep] = useState<Step>('account');
  const [accountData, setAccountData] = useState<AccountData | null>(null);
  const [selectedTier, setSelectedTier] = useState<Tier | undefined>();
  const [loading, setLoading] = useState(false);

  const handleAccountSubmit = async (data: AccountData) => {
    setLoading(true);
    try {
      // In production, this would call API to create account
      // await api.post('/api/auth/register', data);
      console.log('Creating account:', data);
      setAccountData(data);
      setStep('tier');
    } catch (error) {
      console.error('Failed to create account:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTierSelect = (tier: Tier) => {
    setSelectedTier(tier);
  };

  const handleCheckout = async () => {
    if (!selectedTier || !accountData) return;

    setLoading(true);
    try {
      // In production, this would call API to create checkout session
      // const { url } = await api.post('/api/billing/checkout', {
      //   tier: selectedTier,
      //   email: accountData.email,
      //   companyName: accountData.companyName,
      // });
      // window.location.href = url;

      console.log('Creating checkout session for:', {
        tier: selectedTier,
        email: accountData.email,
        companyName: accountData.companyName,
      });

      // Simulate redirect to Stripe
      setStep('checkout');
      setTimeout(() => setStep('success'), 2000);
    } catch (error) {
      console.error('Failed to create checkout session:', error);
    } finally {
      setLoading(false);
    }
  };

  const renderStep = () => {
    switch (step) {
      case 'account':
        return <AccountForm onSubmit={handleAccountSubmit} loading={loading} />;

      case 'tier':
        return (
          <TierSelector
            selectedTier={selectedTier}
            onSelect={handleTierSelect}
            onContinue={handleCheckout}
            loading={loading}
          />
        );

      case 'checkout':
        return (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
            <p className="mt-4 text-muted-foreground">Redirecting to secure checkout...</p>
          </div>
        );

      case 'success':
        return (
          <div className="text-center py-12">
            <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
              <span className="text-3xl">✓</span>
            </div>
            <h2 className="text-2xl font-bold">Welcome to Upstream!</h2>
            <p className="mt-2 text-muted-foreground">
              Your account has been created successfully.
            </p>
            <p className="mt-4">
              <a href="/dashboard" className="text-primary hover:underline">
                Go to Dashboard →
              </a>
            </p>
          </div>
        );
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        {/* Progress Indicator */}
        <div className="mb-8">
          <div className="flex items-center justify-center gap-2 mb-4">
            {['account', 'tier', 'checkout'].map((s, idx) => (
              <div key={s} className="flex items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                    step === s || ['account', 'tier', 'checkout'].indexOf(step) > idx
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {idx + 1}
                </div>
                {idx < 2 && (
                  <div
                    className={`w-12 h-1 mx-2 rounded ${
                      ['account', 'tier', 'checkout'].indexOf(step) > idx
                        ? 'bg-primary'
                        : 'bg-muted'
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
          <div className="flex justify-center gap-8 text-sm text-muted-foreground">
            <span>Account</span>
            <span>Plan</span>
            <span>Payment</span>
          </div>
        </div>

        {renderStep()}

        {/* Back button */}
        {step === 'tier' && (
          <button
            onClick={() => setStep('account')}
            className="mt-4 text-sm text-muted-foreground hover:text-foreground"
          >
            ← Back to account details
          </button>
        )}
      </div>
    </div>
  );
}

export default SignupPage;
