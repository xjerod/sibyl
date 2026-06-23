import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@/test/utils';
import ResetPasswordPage from './page';

let searchParams = new URLSearchParams({ token: 'reset-token' });

const apiMocks = vi.hoisted(() => ({
  confirmPasswordReset: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useSearchParams: () => searchParams,
}));

vi.mock('next/image', () => ({
  default: ({
    priority,
    ...props
  }: React.ImgHTMLAttributes<HTMLImageElement> & { priority?: boolean }) => {
    void priority;
    const { alt = '', ...imageProps } = props;
    return <img alt={alt} {...imageProps} />;
  },
}));

vi.mock('@/lib/api', () => ({
  api: {
    security: {
      confirmPasswordReset: apiMocks.confirmPasswordReset,
    },
  },
}));

describe('ResetPasswordPage', () => {
  beforeEach(() => {
    searchParams = new URLSearchParams({ token: 'reset-token' });
    apiMocks.confirmPasswordReset.mockReset();
  });

  it('confirms a new password with the reset token', async () => {
    apiMocks.confirmPasswordReset.mockResolvedValue({ success: true });
    const { user } = render(<ResetPasswordPage />);

    const form = screen.getByRole('form', { name: 'Set new password' });
    await user.type(within(form).getByLabelText('New Password'), 'new-password');
    await user.type(within(form).getByLabelText('Confirm Password'), 'new-password');
    await user.click(within(form).getByRole('button', { name: 'Update Password' }));

    expect(apiMocks.confirmPasswordReset).toHaveBeenCalledWith({
      token: 'reset-token',
      new_password: 'new-password',
    });
    expect(await screen.findByText('Password updated.')).toBeInTheDocument();
  });

  it('shows a recovery path when the reset token is missing', () => {
    searchParams = new URLSearchParams();

    render(<ResetPasswordPage />);

    expect(screen.getByText('Reset link is missing or expired.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to Sign In' })).toHaveAttribute('href', '/login');
  });
});
