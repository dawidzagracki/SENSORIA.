import { useId, type InputHTMLAttributes, type ReactNode } from "react";
import { combineDescribedBy, FieldMessages } from "./field-helpers";

export type CheckboxProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "id" | "type"
> & {
  description?: ReactNode;
  error?: string;
  hint?: string;
  id?: string;
  label: ReactNode;
  title?: ReactNode;
  trailingContent?: ReactNode;
  variant?: "inline" | "card";
};

export function Checkbox({
  "aria-describedby": userDescribedBy,
  className = "",
  description,
  disabled,
  error,
  hint,
  id,
  label,
  required,
  title,
  trailingContent,
  variant = "inline",
  ...inputProps
}: CheckboxProps) {
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
  const isCard = variant === "card";

  return (
    <div className="space-y-1">
      <label
        className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-card text-body-small text-ink transition-colors focus-within:ring-2 focus-within:ring-accent-action focus-within:ring-offset-2 focus-within:ring-offset-surface ${isCard ? "border border-border bg-surface p-4 hover:bg-surface-muted" : "px-2 py-2 hover:bg-surface-muted"} ${disabled ? "cursor-not-allowed opacity-60" : ""} ${error ? "border border-on-danger" : ""}`}
        htmlFor={inputId}
      >
        <input
          {...inputProps}
          aria-describedby={completeDescribedBy}
          aria-invalid={error ? true : inputProps["aria-invalid"]}
          aria-required={required || undefined}
          className={`h-5 w-5 shrink-0 accent-accent-action focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-action focus-visible:ring-offset-2 focus-visible:ring-offset-surface ${className}`}
          disabled={disabled}
          id={inputId}
          required={required}
          type="checkbox"
        />
        <span className="min-w-0 flex-1">
          {title ? (
            <span className="block font-interface text-label font-bold">
              {title}
            </span>
          ) : null}
          <span className="block">{label}</span>
          {description ? (
            <span
              className="mt-1 block text-caption text-ink-muted"
              id={descriptionId}
            >
              {description}
            </span>
          ) : null}
        </span>
        {trailingContent ? (
          <span className="shrink-0">{trailingContent}</span>
        ) : null}
        {required ? (
          <span className="text-caption text-on-danger">Wymagane</span>
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
