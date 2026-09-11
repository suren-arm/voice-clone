import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AudioDropzone } from '@/features/voices/AudioDropzone';

function audioFile(name = 'clip.wav', type = 'audio/wav', size = 2048) {
  const file = new File(['x'], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

describe('AudioDropzone', () => {
  it('renders the accepted formats and size limit', () => {
    render(<AudioDropzone maxBytes={25 * 1024 * 1024} onFileChange={vi.fn()} />);
    expect(screen.getByTestId('dropzone')).toBeInTheDocument();
    expect(screen.getByText(/WAV, MP3/i)).toBeInTheDocument();
    expect(screen.getByText(/25 MB/)).toBeInTheDocument();
  });

  it('reports a valid selection upward and shows a player', async () => {
    const onFileChange = vi.fn();
    render(<AudioDropzone maxBytes={1024 * 1024} onFileChange={onFileChange} />);

    await userEvent.upload(screen.getByTestId('file-input'), audioFile());

    await waitFor(() => expect(onFileChange).toHaveBeenCalled());
    expect(onFileChange.mock.calls.at(-1)![0]).toMatchObject({ file: expect.any(File) });
    expect(await screen.findByTestId('audio-player')).toBeInTheDocument();
    expect(screen.getByText(/clip\.wav/)).toBeInTheDocument();
  });

  it('rejects an oversized file without reporting a selection', async () => {
    const onFileChange = vi.fn();
    render(<AudioDropzone maxBytes={1024} onFileChange={onFileChange} />);

    await userEvent.upload(screen.getByTestId('file-input'), audioFile('big.wav', 'audio/wav', 99999));

    expect(await screen.findByText(/larger than the 0 MB limit|larger than/i)).toBeInTheDocument();
    expect(onFileChange).toHaveBeenCalledWith(null);
  });

  it('rejects a non-audio file', async () => {
    const onFileChange = vi.fn();
    render(<AudioDropzone maxBytes={1024 * 1024} onFileChange={onFileChange} />);

    // Dropped rather than picked: the file input carries an `accept` filter, so
    // a drop is the path a wrong file type actually reaches the component by.
    fireEvent.drop(screen.getByTestId('dropzone'), {
      dataTransfer: { files: [audioFile('notes.pdf', 'application/pdf')] },
    });

    expect(await screen.findByText(/does not look like an audio file/i)).toBeInTheDocument();
    expect(onFileChange).toHaveBeenCalledWith(null);
  });

  it('accepts a dropped audio file', async () => {
    const onFileChange = vi.fn();
    render(<AudioDropzone maxBytes={1024 * 1024} onFileChange={onFileChange} />);

    fireEvent.drop(screen.getByTestId('dropzone'), {
      dataTransfer: { files: [audioFile()] },
    });

    await waitFor(() => expect(onFileChange).toHaveBeenCalled());
    expect(await screen.findByTestId('audio-player')).toBeInTheDocument();
  });

  it('lets the user pick a different file', async () => {
    const onFileChange = vi.fn();
    render(<AudioDropzone maxBytes={1024 * 1024} onFileChange={onFileChange} />);

    await userEvent.upload(screen.getByTestId('file-input'), audioFile());
    await userEvent.click(await screen.findByTestId('choose-different-file'));

    expect(screen.getByTestId('dropzone')).toBeInTheDocument();
    expect(onFileChange).toHaveBeenLastCalledWith(null);
  });
});
