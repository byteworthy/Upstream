import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface TeamMember {
  email: string;
  role: 'admin' | 'analyst' | 'viewer';
}

interface TeamInvitesProps {
  members: TeamMember[];
  onUpdate: (members: TeamMember[]) => void;
  onNext: () => void;
  onBack: () => void;
  maxMembers: number;
}

const ROLES = [
  { value: 'admin', label: 'Admin', description: 'Full access, can manage team' },
  { value: 'analyst', label: 'Analyst', description: 'Can view and analyze claims' },
  { value: 'viewer', label: 'Viewer', description: 'Read-only access to dashboards' },
];

export function TeamInvites({ members, onUpdate, onNext, onBack, maxMembers }: TeamInvitesProps) {
  const [newEmail, setNewEmail] = useState('');
  const [newRole, setNewRole] = useState<TeamMember['role']>('analyst');
  const [error, setError] = useState('');

  const validateEmail = (email: string) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  };

  const addMember = () => {
    setError('');

    if (!newEmail.trim()) {
      setError('Email is required');
      return;
    }

    if (!validateEmail(newEmail)) {
      setError('Please enter a valid email address');
      return;
    }

    if (members.some((m) => m.email.toLowerCase() === newEmail.toLowerCase())) {
      setError('This email has already been added');
      return;
    }

    if (members.length >= maxMembers) {
      setError(`Your plan allows up to ${maxMembers} team members`);
      return;
    }

    onUpdate([...members, { email: newEmail, role: newRole }]);
    setNewEmail('');
    setNewRole('analyst');
  };

  const removeMember = (email: string) => {
    onUpdate(members.filter((m) => m.email !== email));
  };

  const updateMemberRole = (email: string, role: TeamMember['role']) => {
    onUpdate(members.map((m) => (m.email === email ? { ...m, role } : m)));
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Invite Your Team</CardTitle>
        <CardDescription>
          Add team members who will use Upstream. You can always add more later.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Add Member Form */}
        <div className="p-4 bg-muted/50 rounded-lg space-y-4">
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                type="email"
                value={newEmail}
                onChange={(e) => {
                  setNewEmail(e.target.value);
                  setError('');
                }}
                placeholder="colleague@company.com"
                onKeyDown={(e) => e.key === 'Enter' && addMember()}
              />
            </div>
            <select
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm min-w-[120px]"
              value={newRole}
              onChange={(e) => setNewRole(e.target.value as TeamMember['role'])}
            >
              {ROLES.map((role) => (
                <option key={role.value} value={role.value}>
                  {role.label}
                </option>
              ))}
            </select>
            <Button onClick={addMember}>Add</Button>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <p className="text-xs text-muted-foreground">
            {members.length} of {maxMembers} team members added
          </p>
        </div>

        {/* Role Descriptions */}
        <div className="grid md:grid-cols-3 gap-4">
          {ROLES.map((role) => (
            <div key={role.value} className="p-3 rounded-lg border bg-background">
              <p className="font-medium text-sm">{role.label}</p>
              <p className="text-xs text-muted-foreground">{role.description}</p>
            </div>
          ))}
        </div>

        {/* Member List */}
        {members.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Team Members</p>
            <div className="space-y-2">
              {members.map((member) => (
                <div
                  key={member.email}
                  className="flex items-center justify-between p-3 rounded-lg border"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                      <span className="text-sm font-medium text-primary">
                        {member.email.charAt(0).toUpperCase()}
                      </span>
                    </div>
                    <span className="text-sm">{member.email}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      className="h-8 rounded-md border border-input bg-background px-2 py-1 text-xs"
                      value={member.role}
                      onChange={(e) =>
                        updateMemberRole(member.email, e.target.value as TeamMember['role'])
                      }
                    >
                      {ROLES.map((role) => (
                        <option key={role.value} value={role.value}>
                          {role.label}
                        </option>
                      ))}
                    </select>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => removeMember(member.email)}
                    >
                      Remove
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Skip option */}
        {members.length === 0 && (
          <p className="text-sm text-muted-foreground text-center">
            You can skip this step and invite team members later from Settings.
          </p>
        )}

        {/* Navigation */}
        <div className="flex justify-between pt-4">
          <Button variant="outline" onClick={onBack}>
            Back
          </Button>
          <Button onClick={onNext}>{members.length > 0 ? 'Continue' : 'Skip for now'}</Button>
        </div>
      </CardContent>
    </Card>
  );
}
