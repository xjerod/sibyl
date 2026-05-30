'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useRef, useState } from 'react';
import { toast } from 'sonner';
import { EditableText } from '@/components/editable';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Calendar, Check, Copy, EditPencil, Link, Upload, User } from '@/components/ui/icons';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/hooks';

// Common timezone options
const TIMEZONE_OPTIONS = [
  { value: 'America/Los_Angeles', label: 'Pacific Time (PT)' },
  { value: 'America/Denver', label: 'Mountain Time (MT)' },
  { value: 'America/Chicago', label: 'Central Time (CT)' },
  { value: 'America/New_York', label: 'Eastern Time (ET)' },
  { value: 'Europe/London', label: 'London (GMT/BST)' },
  { value: 'Europe/Paris', label: 'Central European (CET)' },
  { value: 'Europe/Berlin', label: 'Berlin (CET)' },
  { value: 'Asia/Tokyo', label: 'Tokyo (JST)' },
  { value: 'Asia/Shanghai', label: 'Shanghai (CST)' },
  { value: 'Asia/Singapore', label: 'Singapore (SGT)' },
  { value: 'Australia/Sydney', label: 'Sydney (AEST)' },
  { value: 'Pacific/Auckland', label: 'Auckland (NZST)' },
];

function ProfileSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="bg-sc-bg-elevated shadow-card rounded-xl border border-sc-fg-subtle/10 p-8">
        <div className="flex items-start gap-8">
          <div className="w-28 h-28 rounded-full bg-sc-bg-highlight" />
          <div className="flex-1 space-y-4">
            <div className="h-8 w-56 bg-sc-bg-highlight rounded" />
            <div className="h-5 w-40 bg-sc-bg-highlight rounded" />
          </div>
        </div>
      </div>
    </div>
  );
}

interface AvatarUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (url: string) => void;
  currentUrl: string | null;
  isSaving: boolean;
}

function AvatarUploadModal({
  isOpen,
  onClose,
  onSave,
  currentUrl,
  isSaving,
}: AvatarUploadModalProps) {
  const [mode, setMode] = useState<'url' | 'upload'>('url');
  const [urlInput, setUrlInput] = useState(currentUrl || '');
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = useCallback((file: File) => {
    if (!file.type.startsWith('image/')) {
      toast.error('Please select an image file');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error('Image must be under 5MB');
      return;
    }

    const reader = new FileReader();
    reader.onload = e => {
      const dataUrl = e.target?.result as string;
      setPreviewUrl(dataUrl);
      setUrlInput(dataUrl);
    };
    reader.readAsDataURL(file);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFileSelect(file);
    },
    [handleFileSelect]
  );

  const handleSubmit = () => {
    if (!urlInput.trim()) {
      toast.error('Please provide an image URL or upload a file');
      return;
    }
    onSave(urlInput.trim());
  };

  return (
    <Dialog open={isOpen} onOpenChange={open => !open && onClose()}>
      <DialogContent size="md" className="p-0 overflow-hidden">
        {/* Header */}
        <DialogHeader className="mb-0 px-6 py-4 border-b border-sc-fg-subtle/10">
          <DialogTitle>Update Avatar</DialogTitle>
        </DialogHeader>

        {/* Mode Toggle */}
        <div className="flex gap-1 p-1 m-4 bg-sc-bg-highlight rounded-lg">
          <button
            type="button"
            onClick={() => setMode('url')}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sc-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-sc-bg-elevated ${
              mode === 'url'
                ? 'bg-sc-purple text-sc-on-accent shadow-glow-purple'
                : 'text-sc-fg-muted hover:text-sc-fg-primary'
            }`}
          >
            <Link width={16} height={16} />
            URL
          </button>
          <button
            type="button"
            onClick={() => setMode('upload')}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sc-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-sc-bg-elevated ${
              mode === 'upload'
                ? 'bg-sc-purple text-sc-on-accent shadow-glow-purple'
                : 'text-sc-fg-muted hover:text-sc-fg-primary'
            }`}
          >
            <Upload width={16} height={16} />
            Upload
          </button>
        </div>

        {/* Content */}
        <div className="px-6 pb-4">
          {mode === 'url' ? (
            <div className="space-y-4">
              <div>
                <label htmlFor="avatar-url" className="block text-sm text-sc-fg-muted mb-2">
                  Image URL
                </label>
                <input
                  id="avatar-url"
                  type="url"
                  value={urlInput}
                  onChange={e => {
                    setUrlInput(e.target.value);
                    setPreviewUrl(null);
                  }}
                  placeholder="https://example.com/avatar.jpg"
                  className="w-full px-4 py-3 bg-sc-bg-highlight border border-sc-fg-subtle/20 rounded-lg text-sc-fg-primary placeholder:text-sc-fg-subtle transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sc-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-sc-bg-elevated"
                />
              </div>
              <p className="text-xs text-sc-fg-subtle">
                Paste a URL to an image. Supports JPG, PNG, GIF, and WebP.
              </p>
            </div>
          ) : (
            <div
              className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all ${
                dragActive
                  ? 'border-sc-purple bg-sc-purple/10'
                  : 'border-sc-fg-subtle/30 hover:border-sc-fg-subtle/50'
              }`}
              onDragOver={e => {
                e.preventDefault();
                setDragActive(true);
              }}
              onDragLeave={() => setDragActive(false)}
              onDrop={handleDrop}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={e => {
                  const file = e.target.files?.[0];
                  if (file) handleFileSelect(file);
                }}
                className="hidden"
              />
              <Upload width={32} height={32} className="mx-auto text-sc-fg-muted mb-3" />
              <p className="text-sc-fg-secondary mb-1">
                Drag & drop or{' '}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="rounded font-medium text-sc-purple transition-colors duration-200 hover:text-sc-purple/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sc-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-sc-bg-elevated"
                >
                  browse
                </button>
              </p>
              <p className="text-xs text-sc-fg-subtle">Max 5MB. JPG, PNG, GIF, WebP</p>
            </div>
          )}

          {/* Preview */}
          {(previewUrl || (mode === 'url' && urlInput && !urlInput.startsWith('data:'))) && (
            <div className="mt-4 flex items-center gap-4 p-4 bg-sc-bg-highlight rounded-lg">
              <img
                src={previewUrl || urlInput}
                alt="Preview"
                className="w-16 h-16 rounded-full object-cover border-2 border-sc-purple/30"
                onError={e => {
                  (e.target as HTMLImageElement).style.display = 'none';
                }}
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-sc-fg-primary">Preview</p>
                <p className="text-xs text-sc-fg-muted truncate">
                  {previewUrl ? 'Uploaded image' : urlInput}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <DialogFooter className="mt-0 px-6 py-4 border-t border-sc-fg-subtle/10 bg-sc-bg-highlight/50">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!urlInput.trim()}
            loading={isSaving}
            icon={<Check width={16} height={16} />}
          >
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function ProfilePage() {
  const queryClient = useQueryClient();
  const [showAvatarModal, setShowAvatarModal] = useState(false);

  const {
    data: profile,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['user', 'profile'],
    queryFn: api.profile.get,
  });

  const updateMutation = useMutation({
    mutationFn: api.profile.update,
    onSuccess: data => {
      queryClient.setQueryData(['user', 'profile'], data);
      // Also invalidate auth.me so the nav avatar updates
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.me });
      toast.success('Profile updated');
    },
    onError: () => {
      toast.error('Failed to update profile');
    },
  });

  const handleAvatarSave = useCallback(
    async (url: string) => {
      await updateMutation.mutateAsync({ avatar_url: url });
      setShowAvatarModal(false);
    },
    [updateMutation]
  );

  if (isLoading) {
    return <ProfileSkeleton />;
  }

  if (error || !profile) {
    return (
      <div className="bg-sc-bg-elevated shadow-card rounded-xl border border-sc-red/20 p-8">
        <p className="text-sc-red">Failed to load profile. Please try again.</p>
      </div>
    );
  }

  const memberSince = new Date(profile.created_at);
  const memberDays = Math.floor((Date.now() - memberSince.getTime()) / (1000 * 60 * 60 * 24));

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Hero Card - Avatar & Name */}
      <div className="bg-gradient-to-br from-sc-bg-elevated to-sc-bg-highlight shadow-card rounded-xl border border-sc-fg-subtle/10 p-8 relative overflow-hidden">
        {/* Decorative gradient orb */}
        <div className="absolute -top-20 -right-20 w-40 h-40 bg-sc-purple/20 rounded-full blur-3xl" />

        <div className="relative flex items-start gap-6 sm:gap-8">
          {/* Avatar with edit overlay */}
          <button
            type="button"
            onClick={() => setShowAvatarModal(true)}
            aria-label="Change avatar"
            className="relative group shrink-0 rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sc-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-sc-bg-elevated"
          >
            {profile.avatar_url ? (
              <img
                src={profile.avatar_url}
                alt={profile.name || 'Avatar'}
                className="w-24 h-24 sm:w-28 sm:h-28 rounded-full object-cover border-4 border-sc-purple/30 shadow-xl shadow-sc-purple/10 group-hover:border-sc-purple/50 transition-all"
              />
            ) : (
              <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-full bg-sc-bg-elevated border-4 border-sc-fg-subtle/20 flex items-center justify-center group-hover:border-sc-purple/30 transition-all">
                <User width={40} height={40} className="text-sc-fg-muted" />
              </div>
            )}
            {/* Edit overlay */}
            <div className="absolute inset-0 flex items-center justify-center bg-sc-bg-dark/60 rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-200">
              <EditPencil width={24} height={24} className="text-sc-on-accent" />
            </div>
          </button>

          {/* Name & Email */}
          <div className="flex-1 min-w-0 pt-2">
            <EditableText
              value={profile.name || ''}
              onSave={async name => {
                await updateMutation.mutateAsync({ name });
              }}
              placeholder="Your name"
              className="text-2xl sm:text-3xl font-bold text-sc-fg-primary mb-2"
            />
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="text-sc-fg-muted">{profile.email || 'No email set'}</span>
              {profile.email_verified_at && (
                <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 bg-sc-green/10 text-sc-green rounded-full">
                  <Check width={12} height={12} />
                  Verified
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Bio */}
      <div className="bg-sc-bg-elevated shadow-card rounded-xl border border-sc-fg-subtle/10 p-6">
        <h3 className="text-sm font-medium text-sc-fg-muted uppercase tracking-wider mb-3">Bio</h3>
        <EditableText
          value={profile.bio || ''}
          onSave={async bio => {
            await updateMutation.mutateAsync({ bio });
          }}
          placeholder="Tell us about yourself..."
          className="text-sc-fg-secondary leading-relaxed"
          multiline
          rows={4}
        />
      </div>

      {/* Timezone */}
      <div className="bg-sc-bg-elevated shadow-card rounded-xl border border-sc-fg-subtle/10 p-6">
        <h3 className="text-sm font-medium text-sc-fg-muted uppercase tracking-wider mb-3">
          Timezone
        </h3>
        <Select
          value={profile.timezone || ''}
          onValueChange={async value => {
            await updateMutation.mutateAsync({ timezone: value || null });
          }}
        >
          <SelectTrigger className="w-full max-w-md" aria-label="Timezone">
            <SelectValue placeholder="Select timezone..." />
          </SelectTrigger>
          <SelectContent>
            {TIMEZONE_OPTIONS.map(tz => (
              <SelectItem key={tz.value} value={tz.value}>
                {tz.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-sc-fg-muted mt-2">
          Used for displaying dates and scheduling notifications.
        </p>
      </div>

      {/* Account Stats */}
      <div className="bg-sc-bg-elevated shadow-card rounded-xl border border-sc-fg-subtle/10 p-6">
        <h3 className="text-sm font-medium text-sc-fg-muted uppercase tracking-wider mb-4">
          Account
        </h3>
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="flex items-center gap-3 p-4 bg-sc-bg-highlight/50 rounded-lg">
            <div className="w-10 h-10 rounded-lg bg-sc-purple/10 flex items-center justify-center">
              <Calendar width={20} height={20} className="text-sc-purple" />
            </div>
            <div>
              <p className="text-sm text-sc-fg-muted">Member since</p>
              <p className="font-medium text-sc-fg-primary">
                {memberSince.toLocaleDateString(undefined, {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                })}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-4 bg-sc-bg-highlight/50 rounded-lg">
            <div className="w-10 h-10 rounded-lg bg-sc-cyan/10 flex items-center justify-center">
              <User width={20} height={20} className="text-sc-cyan" />
            </div>
            <div>
              <p className="text-sm text-sc-fg-muted">Account age</p>
              <p className="font-medium text-sc-fg-primary">
                {memberDays === 0 ? 'Today' : `${memberDays} day${memberDays === 1 ? '' : 's'}`}
              </p>
            </div>
          </div>
        </div>
        <div className="mt-4 pt-4 border-t border-sc-fg-subtle/10">
          <div className="flex justify-between items-center gap-3 text-sm">
            <span className="text-sc-fg-muted">User ID</span>
            <button
              type="button"
              onClick={async () => {
                await navigator.clipboard.writeText(profile.id);
                toast.success('User ID copied to clipboard');
              }}
              aria-label="Copy user ID"
              className="group inline-flex min-w-0 items-center gap-2 rounded-lg bg-sc-bg-highlight px-2 py-1 transition-colors duration-200 hover:bg-sc-bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sc-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-sc-bg-elevated"
            >
              <code className="truncate font-mono text-xs text-sc-fg-muted">{profile.id}</code>
              <Copy
                width={12}
                height={12}
                className="shrink-0 text-sc-fg-subtle transition-colors duration-200 group-hover:text-sc-cyan"
              />
            </button>
          </div>
        </div>
      </div>

      {/* Avatar Upload Modal */}
      <AvatarUploadModal
        isOpen={showAvatarModal}
        onClose={() => setShowAvatarModal(false)}
        onSave={handleAvatarSave}
        currentUrl={profile.avatar_url}
        isSaving={updateMutation.isPending}
      />
    </div>
  );
}
