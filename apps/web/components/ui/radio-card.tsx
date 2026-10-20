import { useId, type InputHTMLAttributes, type ReactNode } from "react";
import { combineDescribedBy, FieldMessages } from "./field-helpers";

export type RadioCardProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "id" | "type"
> & {
  description: ReactNode;
  error?: string;
  hint?: string;
  id?: string;
  title: ReactNode;
  trailingContent?: ReactNode;
};

export function RadioCard({
  "aria-describedby": userDescribedBy,
  className = "",
  description,
  disabled,
  error,
  hint,
  id,
  required,
  title,
  trailingContent,
  ...props
}: RadioCardProps) {
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
        className={`flex min-h-16 cursor-pointer items-center gap-4 rounded-card border bg-surface p-4 transition-colors has-[:checked]:border-accent-action has-[:checked]:bg-surface-muted focus-within:ring-2 focus-within:ring-accent-action focus-within:ring-offset-2 focus-within:ring-offset-surface ${error ? "border-on-danger" : "border-ink-muted"} ${disabled ? "cursor-not-allowed opacity-60" : "hover:bg-surface-muted"}`}
        htmlFor={inputId}
      >
        <input
          {...props}
          aria-describedby={completeDescribedBy}
          className={`peer sr-only ${className}`}
          disabled={disabled}
          id={inputId}
          required={required}
          type="radio"
        />
        <span
          aria-hidden="true"
          className="h-5 w-5 shrink-0 rounded-pill border-2 border-ink-muted peer-checked:border-accent-action peer-checked:bg-accent-action"
        />
        <span className="min-w-0 flex-1">
          <span className="block font-interface text-label font-bold text-ink">
            {title}
          </span>
          <span
            className="mt-1 block text-body-small text-ink-muted"
            id={descriptionId}
          >
            {description}
          </span>
          {required ? (
            <span className="text-caption text-on-danger">Wybór wymagany</span>
          ) : null}
        </span>
        {trailingContent ? (
          <span className="shrink-0">{trailingContent}</span>
        ) : null}
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
