import { Moon, Sun, Monitor } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useDarkMode } from '@/hooks/useDarkMode';
import { cn } from '@/lib/utils';

interface ThemeToggleProps {
  showLabel?: boolean;
  variant?: 'default' | 'outline' | 'ghost';
  size?: 'default' | 'sm' | 'lg' | 'icon';
}

export function ThemeToggle({
  showLabel = false,
  variant = 'ghost',
  size = 'icon',
}: ThemeToggleProps) {
  const { theme, setTheme, isDark, toggleTheme } = useDarkMode();

  if (showLabel) {
    return (
      <div className="flex items-center gap-1 rounded-lg border p-1">
        <Button
          variant={theme === 'light' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setTheme('light')}
          className="h-8 px-3"
        >
          <Sun className="h-4 w-4 mr-1.5" />
          Light
        </Button>
        <Button
          variant={theme === 'dark' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setTheme('dark')}
          className="h-8 px-3"
        >
          <Moon className="h-4 w-4 mr-1.5" />
          Dark
        </Button>
        <Button
          variant={theme === 'system' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setTheme('system')}
          className="h-8 px-3"
        >
          <Monitor className="h-4 w-4 mr-1.5" />
          System
        </Button>
      </div>
    );
  }

  return (
    <Button
      variant={variant}
      size={size}
      onClick={toggleTheme}
      className={cn('transition-all duration-200', size === 'icon' && 'h-9 w-9')}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      <Sun
        className={cn(
          'h-[1.2rem] w-[1.2rem] transition-all duration-300',
          isDark ? 'rotate-90 scale-0' : 'rotate-0 scale-100'
        )}
      />
      <Moon
        className={cn(
          'absolute h-[1.2rem] w-[1.2rem] transition-all duration-300',
          isDark ? 'rotate-0 scale-100' : '-rotate-90 scale-0'
        )}
      />
      <span className="sr-only">{isDark ? 'Switch to light mode' : 'Switch to dark mode'}</span>
    </Button>
  );
}
