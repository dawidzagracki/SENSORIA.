import { useId, type ReactNode } from "react";

export function useFieldIds(id: string | undefined) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  return {
    fieldId,
    hintId: `${fieldId}-hint`,
    errorId: `${fieldId}-error`,
  };
}

export function combineDescribedBy(
  supplied: string | undefined,
  hintId: string | undefined,
  errorId: string | undefined,
) {
  const ids = [supplied, hintId, errorId]
    .filter((value): value is string => Boolean(value))
    .flatMap((value) => value.split(/\s+/))
    .filter(Boolean);
  return [...new Set(ids)].join(" ") || undefined;
}

export function FieldLabel({
  children,
  htmlFor,
  required,
}: {
  children: ReactNode;
  htmlFor: string;
  required?: boolean;
}) {
  return (
    <label
      className="block font-interface text-label font-bold text-ink"
      htmlFor={htmlFor}
    >
      {children}
      {required ? (
        <span className="ml-1 text-on-danger">
          * <span className="font-normal">(pole wymagane)</span>
        </span>
      ) : null}
    </label>
  );
}

export function FieldMessages({
  error,
  errorId,
  hint,
  hintId,
}: {
  error?: string;
  errorId: string;
  hint?: string;
  hintId: string;
}) {
  return (
    <div className="space-y-1">
      {hint ? (
        <p className="text-caption text-ink-muted" id={hintId}>
          {hint}
        </p>
      ) : null}
      {error ? (
        <p className="text-caption text-on-danger" id={errorId} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function fieldControlClass(error?: string) {
  return `min-h-control-md w-full rounded-card border bg-surface px-4 py-3 font-body text-body-small text-ink placeholder:text-ink-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:cursor-not-allowed disabled:bg-surface-muted disabled:opacity-70 ${error ? "border-on-danger" : "border-ink-muted"}`;
}
