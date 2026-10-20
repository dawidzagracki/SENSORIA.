import { useId, type InputHTMLAttributes, type ReactNode } from "react";
import { combineDescribedBy, FieldMessages } from "./field-helpers";

export type RadioProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "id" | "type"
> & {
  description?: string;
  error?: string;
  hint?: string;
  id?: string;
  label: ReactNode;
};

export function Radio({
  "aria-describedby": userDescribedBy,
  description,
  disabled,
  error,
  hint,
  id,
  label,
  required,
  ...props
}: RadioProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const hintId = `${inputId}-hint`;
  const descriptionId = `${inputId}-description`;
  const errorId = `${inputId}-error`;
  const describedBy = combineDescribedBy(
    userDescribedBy,
    hint ? hintId : undefined,
    description ? descriptionId : undefined,
  );
  const completeDescribedBy = combineDescribedBy(
    describedBy,
    undefined,
    error ? errorId : undefined,
  );

  return (
    <div className="space-y-1">
      <label
        className={`flex min-h-12 cursor-pointer items-start gap-3 rounded-card px-2 py-2 text-body-small text-ink hover:bg-surface-muted ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
        htmlFor={inputId}
      >
        <input
          {...props}
          aria-describedby={completeDescribedBy}
          className="mt-1 h-5 w-5 shrink-0 accent-accent-action focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
          disabled={disabled}
          id={inputId}
          required={required}
          type="radio"
        />
        <span className="min-w-0 flex-1">
          <span className="block">{label}</span>
          {description ? (
            <span
              className="mt-1 block text-caption text-ink-muted"
              id={descriptionId}
            >
              {description}
            </span>
          ) : null}
          {required ? (
            <span className="text-caption text-on-danger">Wymagane</span>
          ) : null}
        </span>
      </label>
      <FieldMessages
        error={error}
        errorId={errorId}
        hint={hint}
        hintId={hintId}
      />
    </div>
  );
}
