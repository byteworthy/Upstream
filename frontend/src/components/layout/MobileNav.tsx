import { X } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  FileText,
  ClipboardList,
  Bell,
  Calendar,
  History,
  Settings,
  type LucideIcon,
} from 'lucide-react';

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

const navItems: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Claim Scores', href: '/claim-scores', icon: FileText },
  { label: 'Work Queue', href: '/work-queue', icon: ClipboardList },
  { label: 'Alerts', href: '/alerts', icon: Bell },
  { label: 'Authorizations', href: '/authorizations', icon: Calendar },
  { label: 'Execution Log', href: '/execution-log', icon: History },
  { label: 'Settings', href: '/settings', icon: Settings },
];

interface MobileNavProps {
  isOpen: boolean;
  onClose: () => void;
}

export function MobileNav({ isOpen, onClose }: MobileNavProps) {
  const location = useLocation();

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm lg:hidden"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-out panel */}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-72 bg-card border-r border-border shadow-lg lg:hidden',
          'transform transition-transform duration-300 ease-in-out',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Header */}
        <div className="flex h-16 items-center justify-between border-b border-border px-4">
          <span className="text-lg font-semibold text-foreground">Upstream</span>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-5 w-5" />
            <span className="sr-only">Close menu</span>
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex flex-col gap-1 p-4">
          {navItems.map((item) => {
            const isActive =
              location.pathname === item.href ||
              (item.href !== '/dashboard' && location.pathname.startsWith(item.href));
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                to={item.href}
                onClick={onClose}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-3 text-sm font-medium transition-colors',
                  'touch-manipulation', // Better touch response
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
              >
                <Icon className="h-5 w-5" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </>
  );
}
