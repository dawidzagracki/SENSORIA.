import type { ButtonHTMLAttributes, ReactNode } from "react";

export type ButtonVariant = "primary" | "secondary" | "text";
export type ButtonSize = "sm" | "md" | "lg";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  loading?: boolean;
  loadingLabel?: string;
  size?: ButtonSize;
  variant?: ButtonVariant;
};

const variants: Record<ButtonVariant, string> = {
  primary:
    "border border-accent-action bg-accent-action text-surface hover:border-accent hover:bg-accent hover:text-ink",
  secondary:
    "border border-accent-action bg-surface text-ink hover:bg-surface-muted",
  text: "border border-transparent bg-transparent text-ink hover:bg-surface-muted",
};

const sizes: Record<ButtonSize, string> = {
  sm: "min-h-control-sm px-3 py-2 text-caption",
  md: "min-h-control-md px-4 py-3 text-label",
  lg: "min-h-control-lg px-6 py-4 text-body-small",
};

export function Button({
  children,
  className = "",
  disabled,
  loading = false,
  loadingLabel = "Ładowanie…",
  size = "md",
  type = "button",
  variant = "primary",
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      aria-busy={loading || undefined}
      className={`inline-flex items-center justify-center gap-2 rounded-pill font-interface font-bold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:cursor-not-allowed disabled:opacity-60 ${sizes[size]} ${variants[variant]} ${className}`}
      disabled={disabled || loading}
      type={type}
    >
      {loading ? (
        <span
          aria-hidden="true"
          className="h-5 w-5 shrink-0 animate-spin rounded-pill border-2 border-current border-r-transparent motion-reduce:animate-none"
        />
      ) : null}
      <span>{children}</span>
      {loading ? <span className="sr-only">{loadingLabel}</span> : null}
    </button>
  );
}
