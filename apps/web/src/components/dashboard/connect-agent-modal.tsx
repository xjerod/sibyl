'use client';

import { ConnectPanel } from '@/components/connect';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Network } from '@/components/ui/icons';

interface ConnectAgentModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ConnectAgentModal({ open, onOpenChange }: ConnectAgentModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-sc-purple via-sc-magenta to-sc-coral flex items-center justify-center shadow-lg shadow-sc-purple/30">
              <Network aria-hidden="true" width={20} height={20} className="text-white" />
            </div>
            <div>
              <DialogTitle>Connect your agent</DialogTitle>
              <DialogDescription>
                Install the CLI or wire Sibyl into any MCP client
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="my-6">
          <ConnectPanel />
        </div>

        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="px-4 py-2 rounded-lg bg-sc-purple text-white text-sm font-medium transition-all hover:bg-sc-purple/90 hover:shadow-lg hover:shadow-sc-purple/25"
          >
            Done
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
