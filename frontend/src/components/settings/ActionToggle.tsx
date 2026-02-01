import { cn } from '@/lib/utils';

interface ActionToggleProps {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}

export function ActionToggle({
  label,
  description,
  checked,
  onChange,
  disabled = false,
}: ActionToggleProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-between p-4 rounded-lg border',
        disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:bg-muted/50',
        checked ? 'border-primary bg-primary/5' : 'border-border'
      )}
      onClick={() => !disabled && onChange(!checked)}
    >
      <div className="flex-1">
        <p className="font-medium text-foreground">{label}</p>
        {description && <p className="text-sm text-muted-foreground mt-0.5">{description}</p>}
      </div>

      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={(e) => {
          e.stopPropagation();
          if (!disabled) onChange(!checked);
        }}
        className={cn(
          'relative inline-flex h-6 w-11 shrink-0 rounded-full border-2 border-transparent transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          checked ? 'bg-primary' : 'bg-muted',
          disabled && 'cursor-not-allowed'
        )}
      >
        <span
          className={cn(
            'pointer-events-none inline-block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform',
            checked ? 'translate-x-5' : 'translate-x-0'
          )}
        />
      </button>
    </div>
  );
}
