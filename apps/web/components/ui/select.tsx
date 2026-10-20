import type { SelectHTMLAttributes } from "react";
import {
  combineDescribedBy,
  FieldLabel,
  FieldMessages,
  fieldControlClass,
  useFieldIds,
} from "./field-helpers";

export type SelectProps = Omit<
  SelectHTMLAttributes<HTMLSelectElement>,
  "id"
> & {
  error?: string;
  hint?: string;
  id?: string;
  label: string;
};

export function Select({
  "aria-describedby": userDescribedBy,
  children,
  className = "",
  error,
  hint,
  id,
  label,
  required,
  ...props
}: SelectProps) {
  const { fieldId, hintId, errorId } = useFieldIds(id);
  const describedBy = combineDescribedBy(
    userDescribedBy,
    hint ? hintId : undefined,
    error ? errorId : undefined,
  );
  return (
    <div className="space-y-2">
      <FieldLabel htmlFor={fieldId} required={required}>
        {label}
      </FieldLabel>
      <select
        {...props}
        aria-describedby={describedBy}
        aria-invalid={error ? true : props["aria-invalid"]}
        aria-required={required || undefined}
        className={`${fieldControlClass(error)} ${className}`}
        id={fieldId}
        required={required}
      >
        {children}
      </select>
      <FieldMessages
        error={error}
        errorId={errorId}
        hint={hint}
        hintId={hintId}
      />
    </div>
  );
}
