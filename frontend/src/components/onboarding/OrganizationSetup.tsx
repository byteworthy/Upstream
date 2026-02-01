import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface OrganizationData {
  organizationName: string;
  organizationType: string;
  npi: string;
  taxId: string;
  address: string;
  city: string;
  state: string;
  zipCode: string;
}

interface OrganizationSetupProps {
  data: OrganizationData;
  onUpdate: (data: Partial<OrganizationData>) => void;
  onNext: () => void;
  onBack: () => void;
}

const ORGANIZATION_TYPES = [
  { value: 'hospital', label: 'Hospital / Health System' },
  { value: 'practice', label: 'Physician Practice' },
  { value: 'billing', label: 'Billing Company' },
  { value: 'clearinghouse', label: 'Clearinghouse' },
  { value: 'other', label: 'Other' },
];

const US_STATES = [
  'AL',
  'AK',
  'AZ',
  'AR',
  'CA',
  'CO',
  'CT',
  'DE',
  'FL',
  'GA',
  'HI',
  'ID',
  'IL',
  'IN',
  'IA',
  'KS',
  'KY',
  'LA',
  'ME',
  'MD',
  'MA',
  'MI',
  'MN',
  'MS',
  'MO',
  'MT',
  'NE',
  'NV',
  'NH',
  'NJ',
  'NM',
  'NY',
  'NC',
  'ND',
  'OH',
  'OK',
  'OR',
  'PA',
  'RI',
  'SC',
  'SD',
  'TN',
  'TX',
  'UT',
  'VT',
  'VA',
  'WA',
  'WV',
  'WI',
  'WY',
];

export function OrganizationSetup({ data, onUpdate, onNext, onBack }: OrganizationSetupProps) {
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = () => {
    const newErrors: Record<string, string> = {};

    if (!data.organizationName.trim()) {
      newErrors.organizationName = 'Organization name is required';
    }
    if (!data.organizationType) {
      newErrors.organizationType = 'Please select an organization type';
    }
    if (data.npi && !/^\d{10}$/.test(data.npi)) {
      newErrors.npi = 'NPI must be 10 digits';
    }
    if (data.taxId && !/^\d{2}-?\d{7}$/.test(data.taxId.replace('-', ''))) {
      newErrors.taxId = 'Invalid Tax ID format';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (validate()) {
      onNext();
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Organization Details</CardTitle>
        <CardDescription>
          Tell us about your organization so we can customize your experience
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Organization Name */}
        <div>
          <label className="text-sm font-medium mb-1.5 block">
            Organization Name <span className="text-destructive">*</span>
          </label>
          <Input
            value={data.organizationName}
            onChange={(e) => onUpdate({ organizationName: e.target.value })}
            placeholder="Acme Health System"
          />
          {errors.organizationName && (
            <p className="text-sm text-destructive mt-1">{errors.organizationName}</p>
          )}
        </div>

        {/* Organization Type */}
        <div>
          <label className="text-sm font-medium mb-1.5 block">
            Organization Type <span className="text-destructive">*</span>
          </label>
          <select
            className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={data.organizationType}
            onChange={(e) => onUpdate({ organizationType: e.target.value })}
          >
            <option value="">Select type...</option>
            {ORGANIZATION_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
          {errors.organizationType && (
            <p className="text-sm text-destructive mt-1">{errors.organizationType}</p>
          )}
        </div>

        {/* NPI & Tax ID */}
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium mb-1.5 block">NPI (Optional)</label>
            <Input
              value={data.npi}
              onChange={(e) => onUpdate({ npi: e.target.value.replace(/\D/g, '').slice(0, 10) })}
              placeholder="1234567890"
              maxLength={10}
            />
            {errors.npi && <p className="text-sm text-destructive mt-1">{errors.npi}</p>}
          </div>
          <div>
            <label className="text-sm font-medium mb-1.5 block">Tax ID (Optional)</label>
            <Input
              value={data.taxId}
              onChange={(e) => onUpdate({ taxId: e.target.value })}
              placeholder="12-3456789"
            />
            {errors.taxId && <p className="text-sm text-destructive mt-1">{errors.taxId}</p>}
          </div>
        </div>

        {/* Address */}
        <div>
          <label className="text-sm font-medium mb-1.5 block">Street Address</label>
          <Input
            value={data.address}
            onChange={(e) => onUpdate({ address: e.target.value })}
            placeholder="123 Healthcare Blvd"
          />
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          <div>
            <label className="text-sm font-medium mb-1.5 block">City</label>
            <Input
              value={data.city}
              onChange={(e) => onUpdate({ city: e.target.value })}
              placeholder="Chicago"
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-1.5 block">State</label>
            <select
              className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={data.state}
              onChange={(e) => onUpdate({ state: e.target.value })}
            >
              <option value="">Select...</option>
              {US_STATES.map((state) => (
                <option key={state} value={state}>
                  {state}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium mb-1.5 block">ZIP Code</label>
            <Input
              value={data.zipCode}
              onChange={(e) => onUpdate({ zipCode: e.target.value.replace(/\D/g, '').slice(0, 5) })}
              placeholder="60601"
              maxLength={5}
            />
          </div>
        </div>

        {/* Navigation */}
        <div className="flex justify-between pt-4">
          <Button variant="outline" onClick={onBack}>
            Back
          </Button>
          <Button onClick={handleNext}>Continue</Button>
        </div>
      </CardContent>
    </Card>
  );
}
