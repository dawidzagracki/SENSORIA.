import type { TextareaHTMLAttributes } from "react";
import {
  combineDescribedBy,
  FieldLabel,
  FieldMessages,
  fieldControlClass,
  useFieldIds,
} from "./field-helpers";

export type TextareaProps = Omit<
  TextareaHTMLAttributes<HTMLTextAreaElement>,
  "id"
> & {
  error?: string;
  hint?: string;
  id?: string;
  label: string;
};

export function Textarea({
  "aria-describedby": userDescribedBy,
  className = "",
  error,
  hint,
  id,
  label,
  required,
  ...props
}: TextareaProps) {
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
      <textarea
        {...props}
        aria-describedby={describedBy}
        aria-invalid={error ? true : props["aria-invalid"]}
        aria-required={required || undefined}
        className={`${fieldControlClass(error)} min-h-24 resize-y ${className}`}
        id={fieldId}
        required={required}
      />
      <FieldMessages
        error={error}
        errorId={errorId}
        hint={hint}
        hintId={hintId}
      />
    </div>
  );
}
