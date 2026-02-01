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
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  customerName?: string;
}

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/claim-scores', icon: FileText, label: 'Claim Scores' },
  { to: '/work-queue', icon: ListTodo, label: 'Work Queue' },
  { to: '/alerts', icon: AlertTriangle, label: 'Alerts' },
  { to: '/authorizations', icon: Calendar, label: 'Authorizations' },
  { to: '/execution-log', icon: History, label: 'Execution Log' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export function Sidebar({ isOpen, onClose, customerName = 'Upstream Healthcare' }: SidebarProps) {
  return (
    <>
      {/* Mobile overlay */}
      {isOpen && <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={onClose} />}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed left-0 top-0 z-50 flex h-full w-64 flex-col bg-card border-r border-border transition-transform duration-300 lg:static lg:translate-x-0',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Logo / Brand */}
        <div className="flex h-16 items-center justify-between border-b border-border px-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold">
              U
            </div>
            <span className="font-semibold text-foreground">{customerName}</span>
          </div>
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={onClose}>
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-4">
          <ul className="space-y-1">
            {navItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  onClick={onClose}
                  className={({ isActive }: { isActive: boolean }) =>
                    cn(
                      'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                    )
                  }
                >
                  <item.icon className="h-5 w-5" />
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        {/* Footer */}
        <div className="border-t border-border p-4">
          <p className="text-xs text-muted-foreground">Claims Intelligence Platform</p>
        </div>
      </aside>
    </>
  );
}
