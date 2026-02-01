import { Menu, LogOut, User, Bell } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import type { User as UserType } from '@/types/api';

interface HeaderProps {
  user?: UserType | null;
  onMenuClick: () => void;
  onLogout: () => void;
}

export function Header({ user, onMenuClick, onLogout }: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-card px-4 lg:px-6">
      {/* Left side - Menu button (mobile) */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" className="lg:hidden" onClick={onMenuClick}>
          <Menu className="h-5 w-5" />
          <span className="sr-only">Toggle menu</span>
        </Button>
        <h1 className="text-lg font-semibold text-foreground lg:text-xl">Upstream Healthcare</h1>
      </div>

      {/* Right side - User menu */}
      <div className="flex items-center gap-2">
        {/* Theme Toggle */}
        <ThemeToggle />

        {/* Notifications */}
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] font-medium text-destructive-foreground">
            3
          </span>
          <span className="sr-only">Notifications</span>
        </Button>

        {/* User info */}
        <div className="hidden items-center gap-2 sm:flex">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted">
            <User className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="hidden md:block">
            <p className="text-sm font-medium text-foreground">
              {user ? `${user.first_name} ${user.last_name}` : 'Guest'}
            </p>
            <p className="text-xs text-muted-foreground">{user?.email || ''}</p>
          </div>
        </div>

        {/* Logout button */}
        <Button variant="ghost" size="icon" onClick={onLogout} title="Logout">
          <LogOut className="h-5 w-5" />
          <span className="sr-only">Logout</span>
        </Button>
      </div>
    </header>
  );
}
