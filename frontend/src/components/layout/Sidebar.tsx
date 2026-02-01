import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  FileText,
  AlertTriangle,
  ListTodo,
  History,
  Settings,
  Calendar,
  X,
  Activity,
  Users,
  Scan,
  Home,
  HeartPulse,
  Zap,
  ChevronRight,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { useCustomer, type SpecialtyType, SPECIALTY_LABELS } from '@/contexts/CustomerContext';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  customerName?: string;
}

interface NavItem {
  to: string;
  icon: LucideIcon;
  label: string;
  badge?: string;
}

// Core navigation items (always shown)
const coreNavItems: NavItem[] = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/claim-scores', icon: FileText, label: 'Claim Scores' },
  { to: '/work-queue', icon: ListTodo, label: 'Work Queue' },
  { to: '/alerts', icon: AlertTriangle, label: 'Alerts' },
  { to: '/execution-log', icon: History, label: 'Execution Log' },
];

// Settings is always at the bottom
const settingsNavItem: NavItem = { to: '/settings', icon: Settings, label: 'Settings' };

// Specialty-specific navigation items with colors
const specialtyNavItems: Record<SpecialtyType, NavItem[]> = {
  DIALYSIS: [{ to: '/specialty/dialysis', icon: Activity, label: 'Dialysis' }],
  ABA: [
    { to: '/authorizations', icon: Calendar, label: 'Authorizations' },
    { to: '/specialty/aba', icon: Users, label: 'ABA Tracking' },
  ],
  IMAGING: [{ to: '/specialty/imaging', icon: Scan, label: 'Imaging PA' }],
  HOME_HEALTH: [
    { to: '/authorizations', icon: Calendar, label: 'Authorizations' },
    { to: '/specialty/homehealth', icon: Home, label: 'Home Health' },
  ],
  PTOT: [{ to: '/specialty/ptot', icon: HeartPulse, label: 'PT/OT' }],
};

// Specialty colors for visual distinction - warm healthcare palette
const specialtyColors: Record<SpecialtyType, string> = {
  DIALYSIS: 'bg-chart-2',
  ABA: 'bg-chart-4',
  IMAGING: 'bg-chart-3',
  HOME_HEALTH: 'bg-primary',
  PTOT: 'bg-chart-5',
};

export function Sidebar({ isOpen, onClose, customerName }: SidebarProps) {
  const { customer, loading } = useCustomer();

  // Build navigation items based on enabled specialties
  const getNavItems = (): NavItem[] => {
    const items = [...coreNavItems];

    if (customer && customer.enabled_specialties) {
      // Collect specialty items, deduplicating by path
      const seen = new Set<string>();
      const specialtyItems: NavItem[] = [];

      for (const specialty of customer.enabled_specialties) {
        const navItems = specialtyNavItems[specialty] || [];
        for (const item of navItems) {
          if (!seen.has(item.to)) {
            seen.add(item.to);
            specialtyItems.push(item);
          }
        }
      }

      // Add specialty items
      items.push(...specialtyItems);
    }

    // Settings always at the end
    items.push(settingsNavItem);

    return items;
  };

  const navItems = getNavItems();
  const displayName = customer?.name || customerName || 'Upstream';
  const primarySpecialty = customer?.specialty_type;

  return (
    <>
      {/* Mobile overlay with blur */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Premium Sidebar */}
      <aside
        className={cn(
          'fixed left-0 top-0 z-50 flex h-full w-72 flex-col',
          'bg-card/95 backdrop-blur-xl border-r border-border/50',
          'transition-transform duration-300 ease-out',
          'lg:static lg:translate-x-0',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Premium Header with gradient accent */}
        <div className="relative flex h-20 items-center justify-between px-5 border-b border-border/50">
          {/* Subtle gradient accent line */}
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-primary to-transparent opacity-60" />

          <div className="flex items-center gap-3">
            {/* Premium Logo Mark */}
            <div className="relative">
              <div
                className={cn(
                  'flex h-10 w-10 items-center justify-center rounded-xl',
                  'bg-gradient-to-br from-primary to-upstream-700',
                  'text-white font-bold text-lg shadow-md',
                  'transition-transform duration-200 hover:scale-105'
                )}
              >
                U
              </div>
              {/* Live indicator dot */}
              <div className="absolute -top-0.5 -right-0.5 h-3 w-3 rounded-full bg-success-500 border-2 border-card live-indicator" />
            </div>

            <div className="flex flex-col">
              <span className="font-semibold text-foreground tracking-tight truncate max-w-[160px]">
                {displayName}
              </span>
              {primarySpecialty && (
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <span
                    className={cn('h-1.5 w-1.5 rounded-full', specialtyColors[primarySpecialty])}
                  />
                  {SPECIALTY_LABELS[primarySpecialty]}
                </span>
              )}
            </div>
          </div>

          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden hover:bg-muted/80"
            onClick={onClose}
            aria-label="Close sidebar"
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Premium Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="Main navigation">
          {loading ? (
            <div className="space-y-2 px-2">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="skeleton h-10 w-full" />
              ))}
            </div>
          ) : (
            <ul className="space-y-1">
              {navItems.map((item, index) => (
                <li
                  key={item.to}
                  className="animate-in opacity-0"
                  style={{ animationDelay: `${index * 0.03}s` }}
                >
                  <NavLink
                    to={item.to}
                    onClick={onClose}
                    className={({ isActive }: { isActive: boolean }) =>
                      cn(
                        'group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium',
                        'transition-all duration-200 ease-out',
                        isActive
                          ? 'bg-primary text-primary-foreground shadow-md shadow-primary/20'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                      )
                    }
                  >
                    {({ isActive }: { isActive: boolean }) => (
                      <>
                        <item.icon
                          className={cn(
                            'h-5 w-5 flex-shrink-0 transition-transform duration-200',
                            !isActive && 'group-hover:scale-110'
                          )}
                        />
                        <span className="flex-1">{item.label}</span>
                        {item.badge && (
                          <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-primary/10 text-primary">
                            {item.badge}
                          </span>
                        )}
                        {!isActive && (
                          <ChevronRight className="h-4 w-4 opacity-0 -translate-x-2 transition-all duration-200 group-hover:opacity-50 group-hover:translate-x-0" />
                        )}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          )}
        </nav>

        {/* Premium Footer */}
        <div className="border-t border-border/50 p-4">
          {/* Active Modules Indicator */}
          {customer?.enabled_specialties && customer.enabled_specialties.length > 1 && (
            <div className="mb-3 flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Active modules:</span>
              <div className="flex -space-x-1">
                {customer.enabled_specialties.slice(0, 4).map((specialty) => (
                  <div
                    key={specialty}
                    className={cn(
                      'h-5 w-5 rounded-full border-2 border-card flex items-center justify-center',
                      specialtyColors[specialty]
                    )}
                    title={SPECIALTY_LABELS[specialty]}
                  >
                    <span className="text-[8px] font-bold text-white">
                      {specialty.charAt(0)}
                    </span>
                  </div>
                ))}
                {customer.enabled_specialties.length > 4 && (
                  <div className="h-5 w-5 rounded-full border-2 border-card bg-muted flex items-center justify-center">
                    <span className="text-[8px] font-medium text-muted-foreground">
                      +{customer.enabled_specialties.length - 4}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Platform branding */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Zap className="h-3.5 w-3.5 text-primary" />
            <span>Upstream Intelligence Platform</span>
          </div>
        </div>
      </aside>
    </>
  );
}
