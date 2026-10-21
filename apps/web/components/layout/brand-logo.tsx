/** SENSORIA wordmark: extra-bold geometric sans with a pink full stop. */
export function BrandLogo({ className = "" }: { className?: string }) {
  return (
    <span className={`font-display font-extrabold tracking-tight ${className}`}>
      SENSORIA<span className="text-accent">.</span>
    </span>
  );
}
