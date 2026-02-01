import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface ComplianceData {
  acceptedBaa: boolean;
  acceptedTerms: boolean;
  acceptedPrivacy: boolean;
}

interface ComplianceAgreementsProps {
  data: ComplianceData;
  onUpdate: (data: Partial<ComplianceData>) => void;
  onComplete: () => void;
  onBack: () => void;
}

export function ComplianceAgreements({
  data,
  onUpdate,
  onComplete,
  onBack,
}: ComplianceAgreementsProps) {
  const allAccepted = data.acceptedBaa && data.acceptedTerms && data.acceptedPrivacy;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Compliance & Agreements</CardTitle>
        <CardDescription>
          Review and accept the required agreements to complete your setup
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* BAA */}
        <div className="p-4 rounded-lg border">
          <div className="flex items-start gap-3">
            <input
              type="checkbox"
              id="baa"
              checked={data.acceptedBaa}
              onChange={(e) => onUpdate({ acceptedBaa: e.target.checked })}
              className="mt-1"
            />
            <div className="flex-1">
              <label htmlFor="baa" className="font-medium cursor-pointer">
                Business Associate Agreement (BAA)
              </label>
              <p className="text-sm text-muted-foreground mt-1">
                Required for HIPAA compliance. This agreement governs how we handle Protected Health
                Information (PHI).
              </p>
              <a
                href="/docs/legal/baa"
                target="_blank"
                className="text-sm text-primary hover:underline mt-2 inline-block"
              >
                View full BAA document
              </a>
            </div>
          </div>
        </div>

        {/* Terms of Service */}
        <div className="p-4 rounded-lg border">
          <div className="flex items-start gap-3">
            <input
              type="checkbox"
              id="terms"
              checked={data.acceptedTerms}
              onChange={(e) => onUpdate({ acceptedTerms: e.target.checked })}
              className="mt-1"
            />
            <div className="flex-1">
              <label htmlFor="terms" className="font-medium cursor-pointer">
                Terms of Service
              </label>
              <p className="text-sm text-muted-foreground mt-1">
                Our terms govern your use of Upstream Healthcare services, including usage limits,
                payment terms, and service level agreements.
              </p>
              <a
                href="/terms"
                target="_blank"
                className="text-sm text-primary hover:underline mt-2 inline-block"
              >
                View Terms of Service
              </a>
            </div>
          </div>
        </div>

        {/* Privacy Policy */}
        <div className="p-4 rounded-lg border">
          <div className="flex items-start gap-3">
            <input
              type="checkbox"
              id="privacy"
              checked={data.acceptedPrivacy}
              onChange={(e) => onUpdate({ acceptedPrivacy: e.target.checked })}
              className="mt-1"
            />
            <div className="flex-1">
              <label htmlFor="privacy" className="font-medium cursor-pointer">
                Privacy Policy
              </label>
              <p className="text-sm text-muted-foreground mt-1">
                Learn how we collect, use, and protect your information. We are committed to data
                privacy and transparency.
              </p>
              <a
                href="/privacy"
                target="_blank"
                className="text-sm text-primary hover:underline mt-2 inline-block"
              >
                View Privacy Policy
              </a>
            </div>
          </div>
        </div>

        {/* Summary */}
        <div className="p-4 bg-muted/50 rounded-lg">
          <h4 className="font-medium mb-2">What happens next?</h4>
          <ul className="text-sm text-muted-foreground space-y-1">
            <li>1. Your account will be activated immediately</li>
            <li>2. Team invitations will be sent via email</li>
            <li>3. You can start uploading claims data right away</li>
            <li>4. Our support team is available to help with integration</li>
          </ul>
        </div>

        {/* Navigation */}
        <div className="flex justify-between pt-4">
          <Button variant="outline" onClick={onBack}>
            Back
          </Button>
          <Button onClick={onComplete} disabled={!allAccepted}>
            Complete Setup
          </Button>
        </div>

        {!allAccepted && (
          <p className="text-sm text-muted-foreground text-center">
            Please accept all agreements to continue
          </p>
        )}
      </CardContent>
    </Card>
  );
}
