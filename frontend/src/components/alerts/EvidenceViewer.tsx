import { useState } from 'react';
import { ChevronDown, ChevronRight, Copy, Check } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface EvidenceViewerProps {
  evidence: Record<string, unknown>;
}

export function EvidenceViewer({ evidence }: EvidenceViewerProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [copied, setCopied] = useState(false);

  const jsonString = JSON.stringify(evidence, null, 2);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isEmpty = Object.keys(evidence).length === 0;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle
            className="text-base flex items-center gap-2 cursor-pointer"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
            Evidence Payload
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            disabled={isEmpty}
            className="text-muted-foreground"
          >
            {copied ? (
              <>
                <Check className="h-4 w-4 mr-1" />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-4 w-4 mr-1" />
                Copy JSON
              </>
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent className={cn(!isExpanded && 'hidden')}>
        {isEmpty ? (
          <p className="text-sm text-muted-foreground">No evidence data available</p>
        ) : (
          <pre className="bg-muted rounded-lg p-4 overflow-auto max-h-96 text-sm text-foreground">
            <code>{jsonString}</code>
          </pre>
        )}
      </CardContent>
    </Card>
  );
}
