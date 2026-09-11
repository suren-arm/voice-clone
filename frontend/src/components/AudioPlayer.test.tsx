import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { AudioPlayer } from '@/components/AudioPlayer';

describe('AudioPlayer', () => {
  it('shows the known duration before metadata loads', () => {
    render(<AudioPlayer src="blob:x" durationSeconds={8} />);
    expect(screen.getByText('0:08')).toBeInTheDocument();
    expect(screen.getByText('0:00')).toBeInTheDocument();
  });

  it('exposes an accessible play control', async () => {
    render(<AudioPlayer src="blob:x" durationSeconds={8} label="the recording" />);
    const play = screen.getByRole('button', { name: /play the recording/i });
    await userEvent.click(play);
    expect(play).toBeInTheDocument();
  });

  it('disables the scrubber while the duration is unknown', () => {
    render(<AudioPlayer src="blob:x" />);
    expect(screen.getByRole('slider', { name: /seek/i })).toBeDisabled();
  });

  it('enables the scrubber once a duration is known', () => {
    render(<AudioPlayer src="blob:x" durationSeconds={12} />);
    expect(screen.getByRole('slider', { name: /seek/i })).toBeEnabled();
  });
});
