import {
  useFieldIds,
  combineDescribedBy,
  FieldLabel,
  FieldMessages,
  fieldControlClass,
} from "./field-helpers";
import type { InputHTMLAttributes } from "react";

export type TextFieldProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "id"
> & {
  error?: string;
  hint?: string;
  id?: string;
  label: string;
};

export function TextField({
  "aria-describedby": userDescribedBy,
  error,
  hint,
  id,
  label,
  required,
  ...inputProps
}: TextFieldProps) {
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
      <input
        {...inputProps}
        aria-describedby={describedBy}
        aria-invalid={error ? true : inputProps["aria-invalid"]}
        aria-required={required || undefined}
        className={`${fieldControlClass(error)} ${inputProps.className ?? ""}`}
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
