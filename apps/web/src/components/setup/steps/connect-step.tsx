'use client';

import { ConnectPanel } from '@/components/connect';
import { Button } from '@/components/ui';
import { CheckCircle } from '@/components/ui/icons';

interface ConnectStepProps {
  onFinish: () => void;
}

export function ConnectStep({ onFinish }: ConnectStepProps) {
  return (
    <div className="p-8">
      {/* Success Icon */}
      <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-sc-green/20 to-sc-cyan/20 flex items-center justify-center">
        <CheckCircle aria-hidden="true" width={40} height={40} className="text-sc-green" />
      </div>

      {/* Content */}
      <div className="text-center mb-8">
        <h2 className="text-2xl font-semibold text-sc-fg-primary mb-3">Setup Complete!</h2>
        <p className="text-sc-fg-muted leading-relaxed max-w-md mx-auto">
          Sibyl is ready. Here's how to start using it from the terminal or your AI agent.
        </p>
      </div>

      {/* Connect paths */}
      <div className="mb-8">
        <ConnectPanel />
      </div>

      {/* CTA */}
      <Button
        type="button"
        variant="primary"
        size="lg"
        onClick={onFinish}
        className="w-full focus-visible:ring-offset-sc-bg-elevated"
      >
        Start Using Sibyl
      </Button>
    </div>
  );
}
