interface SpinnerProps {
  label?: string;
  large?: boolean;
}

export function Spinner({ label = 'Loading', large = false }: SpinnerProps) {
  return (
    <span className="progress-note">
      <span className={large ? 'spinner spinner--lg' : 'spinner'} aria-hidden="true" />
      <span className="sr-only">{label}</span>
      <span aria-hidden="true">{label}</span>
    </span>
  );
}
