import { useState, useMemo } from 'react';
import { ChevronLeft, ChevronRight, Download } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ExpirationCard } from './ExpirationCard';
import type { Authorization } from '@/types/api';
import { cn } from '@/lib/utils';

interface AuthorizationCalendarProps {
  authorizations: Authorization[];
  onExportCSV: () => void;
}

const DAYS_OF_WEEK = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

// Get initial timestamp outside of component to avoid React strict mode issues
const getInitialTimestamp = () => Date.now();

export function AuthorizationCalendar({ authorizations, onExportCSV }: AuthorizationCalendarProps) {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [now] = useState(getInitialTimestamp);

  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth();

  // Get days in current month
  const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
  const firstDayOfMonth = new Date(currentYear, currentMonth, 1).getDay();

  // Build authorization map by date
  const authorizationsByDate = useMemo(() => {
    const map = new Map<string, Authorization[]>();
    authorizations.forEach((auth) => {
      const endDate = auth.end_date.split('T')[0];
      const existing = map.get(endDate) || [];
      map.set(endDate, [...existing, auth]);
    });
    return map;
  }, [authorizations]);

  // Get authorizations expiring on selected date
  const selectedDateAuths = useMemo(() => {
    if (!selectedDate) return [];
    const dateKey = selectedDate.toISOString().split('T')[0];
    return authorizationsByDate.get(dateKey) || [];
  }, [selectedDate, authorizationsByDate]);

  // Navigate months
  const goToPrevMonth = () => {
    setCurrentDate(new Date(currentYear, currentMonth - 1, 1));
  };

  const goToNextMonth = () => {
    setCurrentDate(new Date(currentYear, currentMonth + 1, 1));
  };

  const goToToday = () => {
    setCurrentDate(new Date());
    setSelectedDate(new Date());
  };

  // Get color for day based on expiring authorizations
  const getDayColor = (day: number) => {
    const date = new Date(currentYear, currentMonth, day);
    const dateKey = date.toISOString().split('T')[0];
    const auths = authorizationsByDate.get(dateKey);

    if (!auths || auths.length === 0) return null;

    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const dayDate = new Date(date);
    dayDate.setHours(0, 0, 0, 0);
    const daysUntil = Math.ceil((dayDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));

    if (daysUntil < 0) return 'bg-muted text-muted-foreground'; // Past
    if (daysUntil <= 7) return 'bg-danger-500 text-white'; // Critical
    if (daysUntil <= 14) return 'bg-warning-500 text-white'; // Warning
    if (daysUntil <= 30) return 'bg-warning-400 text-white'; // Caution
    return 'bg-success-500 text-white'; // Good
  };

  const getAuthCountForDay = (day: number) => {
    const date = new Date(currentYear, currentMonth, day);
    const dateKey = date.toISOString().split('T')[0];
    return authorizationsByDate.get(dateKey)?.length || 0;
  };

  const isToday = (day: number) => {
    const today = new Date();
    return (
      day === today.getDate() &&
      currentMonth === today.getMonth() &&
      currentYear === today.getFullYear()
    );
  };

  const isSelected = (day: number) => {
    if (!selectedDate) return false;
    return (
      day === selectedDate.getDate() &&
      currentMonth === selectedDate.getMonth() &&
      currentYear === selectedDate.getFullYear()
    );
  };

  // Generate calendar days
  const calendarDays = [];
  // Empty cells before first day
  for (let i = 0; i < firstDayOfMonth; i++) {
    calendarDays.push(null);
  }
  // Days of month
  for (let day = 1; day <= daysInMonth; day++) {
    calendarDays.push(day);
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Authorization Calendar</CardTitle>
              <CardDescription>
                View authorization expiration dates. Click a date to see details.
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={onExportCSV}>
              <Download className="h-4 w-4 mr-2" />
              Export CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Calendar Header */}
          <div className="flex items-center justify-between mb-4">
            <Button variant="ghost" size="icon" onClick={goToPrevMonth}>
              <ChevronLeft className="h-5 w-5" />
            </Button>
            <div className="flex items-center gap-4">
              <span className="text-lg font-semibold">
                {MONTHS[currentMonth]} {currentYear}
              </span>
              <Button variant="outline" size="sm" onClick={goToToday}>
                Today
              </Button>
            </div>
            <Button variant="ghost" size="icon" onClick={goToNextMonth}>
              <ChevronRight className="h-5 w-5" />
            </Button>
          </div>

          {/* Days of Week Header */}
          <div className="grid grid-cols-7 gap-1 mb-2">
            {DAYS_OF_WEEK.map((day) => (
              <div key={day} className="text-center text-sm font-medium text-muted-foreground py-2">
                {day}
              </div>
            ))}
          </div>

          {/* Calendar Grid */}
          <div className="grid grid-cols-7 gap-1">
            {calendarDays.map((day, index) => {
              if (day === null) {
                return <div key={`empty-${index}`} className="aspect-square" />;
              }

              const dayColor = getDayColor(day);
              const authCount = getAuthCountForDay(day);

              return (
                <button
                  key={day}
                  onClick={() => setSelectedDate(new Date(currentYear, currentMonth, day))}
                  className={cn(
                    'aspect-square flex flex-col items-center justify-center rounded-md text-sm transition-colors',
                    'hover:bg-muted focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
                    isSelected(day) && 'ring-2 ring-primary ring-offset-2',
                    isToday(day) && !dayColor && 'border-2 border-primary',
                    dayColor || 'hover:bg-muted'
                  )}
                >
                  <span className={cn('font-medium', !dayColor && 'text-foreground')}>{day}</span>
                  {authCount > 0 && (
                    <span
                      className={cn('text-xs', dayColor ? 'opacity-90' : 'text-muted-foreground')}
                    >
                      {authCount}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Legend */}
          <div className="mt-6 flex flex-wrap items-center gap-4 text-sm">
            <span className="text-muted-foreground font-medium">Legend:</span>
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 rounded bg-danger-500" />
              <span className="text-muted-foreground">≤7 days</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 rounded bg-warning-500" />
              <span className="text-muted-foreground">8-14 days</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 rounded bg-warning-400" />
              <span className="text-muted-foreground">15-30 days</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 rounded bg-success-500" />
              <span className="text-muted-foreground">&gt;30 days</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Selected Date Details */}
      {selectedDate && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Authorizations Expiring on{' '}
              {selectedDate.toLocaleDateString('en-US', {
                weekday: 'long',
                month: 'long',
                day: 'numeric',
                year: 'numeric',
              })}
            </CardTitle>
            <CardDescription>
              {selectedDateAuths.length === 0
                ? 'No authorizations expire on this date'
                : `${selectedDateAuths.length} authorization${selectedDateAuths.length !== 1 ? 's' : ''} expiring`}
            </CardDescription>
          </CardHeader>
          {selectedDateAuths.length > 0 && (
            <CardContent className="space-y-3">
              {selectedDateAuths.map((auth) => (
                <ExpirationCard key={auth.id} authorization={auth} currentTime={now} />
              ))}
            </CardContent>
          )}
        </Card>
      )}
    </div>
  );
}
