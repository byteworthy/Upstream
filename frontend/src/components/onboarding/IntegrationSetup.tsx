import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface IntegrationData {
  ehrSystem: string;
  clearinghouse: string;
  practiceManagement: string;
  dataFormat: string;
}

interface IntegrationSetupProps {
  data: IntegrationData;
  onUpdate: (data: Partial<IntegrationData>) => void;
  onNext: () => void;
  onBack: () => void;
}

const EHR_SYSTEMS = [
  { value: 'epic', label: 'Epic', popular: true },
  { value: 'cerner', label: 'Cerner', popular: true },
  { value: 'meditech', label: 'MEDITECH', popular: true },
  { value: 'allscripts', label: 'Allscripts', popular: false },
  { value: 'athena', label: 'athenahealth', popular: false },
  { value: 'nextgen', label: 'NextGen', popular: false },
  { value: 'eclinicalworks', label: 'eClinicalWorks', popular: false },
  { value: 'other', label: 'Other', popular: false },
  { value: 'none', label: 'Not sure / None', popular: false },
];

const CLEARINGHOUSES = [
  { value: 'change', label: 'Change Healthcare', popular: true },
  { value: 'availity', label: 'Availity', popular: true },
  { value: 'waystar', label: 'Waystar', popular: true },
  { value: 'trizetto', label: 'Trizetto', popular: false },
  { value: 'officeally', label: 'Office Ally', popular: false },
  { value: 'other', label: 'Other', popular: false },
  { value: 'none', label: 'Not sure / None', popular: false },
];

const DATA_FORMATS = [
  { value: '837', label: 'ANSI X12 837', description: 'Standard electronic claim format' },
  { value: 'csv', label: 'CSV Export', description: 'Spreadsheet export from your system' },
  { value: 'api', label: 'Direct API', description: 'Real-time API integration' },
  { value: 'hl7', label: 'HL7 FHIR', description: 'Modern healthcare interoperability' },
  { value: 'unsure', label: 'Not sure', description: "We'll help you figure it out" },
];

export function IntegrationSetup({ data, onUpdate, onNext, onBack }: IntegrationSetupProps) {
  const [showAllEhr, setShowAllEhr] = useState(false);
  const [showAllClearinghouse, setShowAllClearinghouse] = useState(false);

  const displayedEhrSystems = showAllEhr
    ? EHR_SYSTEMS
    : EHR_SYSTEMS.filter((s) => s.popular || s.value === data.ehrSystem);

  const displayedClearinghouses = showAllClearinghouse
    ? CLEARINGHOUSES
    : CLEARINGHOUSES.filter((s) => s.popular || s.value === data.clearinghouse);

  return (
    <Card>
      <CardHeader>
        <CardTitle>System Integrations</CardTitle>
        <CardDescription>
          Help us understand your current technology stack for seamless integration
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-8">
        {/* EHR System */}
        <div>
          <label className="text-sm font-medium mb-3 block">What EHR system do you use?</label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {displayedEhrSystems.map((system) => (
              <button
                key={system.value}
                onClick={() => onUpdate({ ehrSystem: system.value })}
                className={`p-3 rounded-lg border text-sm text-left transition-colors ${
                  data.ehrSystem === system.value
                    ? 'border-primary bg-primary/5 text-primary'
                    : 'border-border hover:border-primary/50'
                }`}
              >
                {system.label}
              </button>
            ))}
          </div>
          {!showAllEhr && (
            <Button variant="link" className="mt-2 p-0 h-auto" onClick={() => setShowAllEhr(true)}>
              Show more options
            </Button>
          )}
        </div>

        {/* Clearinghouse */}
        <div>
          <label className="text-sm font-medium mb-3 block">What clearinghouse do you use?</label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {displayedClearinghouses.map((ch) => (
              <button
                key={ch.value}
                onClick={() => onUpdate({ clearinghouse: ch.value })}
                className={`p-3 rounded-lg border text-sm text-left transition-colors ${
                  data.clearinghouse === ch.value
                    ? 'border-primary bg-primary/5 text-primary'
                    : 'border-border hover:border-primary/50'
                }`}
              >
                {ch.label}
              </button>
            ))}
          </div>
          {!showAllClearinghouse && (
            <Button
              variant="link"
              className="mt-2 p-0 h-auto"
              onClick={() => setShowAllClearinghouse(true)}
            >
              Show more options
            </Button>
          )}
        </div>

        {/* Data Format */}
        <div>
          <label className="text-sm font-medium mb-3 block">
            How would you like to send us data?
          </label>
          <div className="space-y-3">
            {DATA_FORMATS.map((format) => (
              <button
                key={format.value}
                onClick={() => onUpdate({ dataFormat: format.value })}
                className={`w-full p-4 rounded-lg border text-left transition-colors ${
                  data.dataFormat === format.value
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:border-primary/50'
                }`}
              >
                <p
                  className={`font-medium ${data.dataFormat === format.value ? 'text-primary' : ''}`}
                >
                  {format.label}
                </p>
                <p className="text-sm text-muted-foreground">{format.description}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Navigation */}
        <div className="flex justify-between pt-4">
          <Button variant="outline" onClick={onBack}>
            Back
          </Button>
          <Button onClick={onNext}>Continue</Button>
        </div>
      </CardContent>
    </Card>
  );
}
