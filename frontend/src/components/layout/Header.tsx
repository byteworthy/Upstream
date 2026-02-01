import { Menu, LogOut, User, Bell, Search, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import { cn } from '@/lib/utils';
import type { User as UserType } from '@/types/api';

interface HeaderProps {
  user?: UserType | null;
  onMenuClick: () => void;
  onLogout: () => void;
}

export function Header({ user, onMenuClick, onLogout }: HeaderProps) {
  return (
    <header
      className={cn(
        'sticky top-0 z-30 flex h-16 items-center justify-between',
        'border-b border-border/50 bg-card/80 backdrop-blur-xl',
        'px-4 lg:px-6'
      )}
    >
      {/* Left side - Menu button (mobile) + Search */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden hover:bg-muted/80"
          onClick={onMenuClick}
        >
          <Menu className="h-5 w-5" />
          <span className="sr-only">Toggle menu</span>
        </Button>

        {/* Global Search - Premium Style */}
        <div className="hidden md:flex items-center gap-2">
          <div
            className={cn(
              'flex items-center gap-2 rounded-xl px-4 py-2',
              'bg-muted/50 border border-border/50',
              'text-muted-foreground text-sm',
              'transition-all duration-200 hover:bg-muted hover:border-border',
              'cursor-pointer w-64'
            )}
          >
            <Search className="h-4 w-4" />
            <span>Search claims, alerts...</span>
            <kbd className="ml-auto hidden lg:inline-flex h-5 items-center gap-1 rounded border border-border/50 bg-background px-1.5 text-[10px] font-medium text-muted-foreground">
              ⌘K
            </kbd>
          </div>
        </div>
      </div>

      {/* Right side - Actions & User */}
      <div className="flex items-center gap-1 lg:gap-2">
        {/* AI Assistant Quick Action */}
        <Button
          variant="ghost"
          size="sm"
          className={cn(
            'hidden sm:flex items-center gap-2 rounded-xl',
            'text-primary hover:text-primary hover:bg-primary/10',
            'transition-colors duration-200'
          )}
        >
          <Sparkles className="h-4 w-4" />
          <span className="hidden lg:inline text-sm font-medium">AI Assist</span>
        </Button>

        {/* Theme Toggle */}
        <ThemeToggle />

        {/* Notifications - Premium Bell */}
        <Button variant="ghost" size="icon" className="relative hover:bg-muted/80">
          <Bell className="h-5 w-5" />
          <span
            className={cn(
              'absolute -right-0.5 -top-0.5',
              'flex h-4 w-4 items-center justify-center',
              'rounded-full bg-danger-500 text-[10px] font-medium text-white',
              'ring-2 ring-card'
            )}
          >
            3
          </span>
          <span className="sr-only">Notifications</span>
        </Button>

        {/* Divider */}
        <div className="hidden sm:block h-6 w-px bg-border/50 mx-1" />

        {/* User Profile - Premium Avatar */}
        <div className="hidden items-center gap-3 sm:flex">
          <div
            className={cn(
              'relative flex h-9 w-9 items-center justify-center',
              'rounded-xl bg-gradient-to-br from-primary/20 to-primary/10',
              'border border-primary/20 transition-transform duration-200 hover:scale-105'
            )}
          >
            <User className="h-4 w-4 text-primary" />
            {/* Online indicator */}
            <div className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full bg-success-500 border-2 border-card" />
          </div>
          <div className="hidden lg:block">
            <p className="text-sm font-medium text-foreground leading-tight">
              {user ? `${user.first_name} ${user.last_name}` : 'Guest'}
            </p>
            <p className="text-xs text-muted-foreground">{user?.email || ''}</p>
          </div>
        </div>

        {/* Logout button */}
        <Button
          variant="ghost"
          size="icon"
          onClick={onLogout}
          title="Logout"
          className="hover:bg-danger-500/10 hover:text-danger-500 transition-colors duration-200"
        >
          <LogOut className="h-5 w-5" />
          <span className="sr-only">Logout</span>
        </Button>
      </div>
    </header>
  );
}
