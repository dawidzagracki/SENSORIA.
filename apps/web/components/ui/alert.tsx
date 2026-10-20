import type { ReactNode } from "react";

export type AlertVariant = "info" | "success" | "warning" | "error";
export type AlertProps = {
  children: ReactNode;
  icon?: ReactNode;
  title?: string;
  variant?: AlertVariant;
};

const variants: Record<AlertVariant, string> = {
  info: "border-info bg-info text-on-info",
  success: "border-success bg-success text-on-success",
  warning: "border-warning bg-warning text-on-warning",
  error: "border-danger bg-danger text-on-danger",
};

export function Alert({ children, icon, title, variant = "info" }: AlertProps) {
  const urgent = variant === "error";
  return (
    <div
      aria-live={urgent ? "assertive" : "polite"}
      className={`flex gap-3 rounded-card border p-4 ${variants[variant]}`}
      role={urgent ? "alert" : "status"}
    >
      {icon ? (
        <span aria-hidden="true" className="shrink-0">
          {icon}
        </span>
      ) : null}
      <div className="min-w-0">
        {title ? (
          <p className="font-interface text-label font-bold">{title}</p>
        ) : null}
        <div className="text-body-small">{children}</div>
      </div>
    </div>
  );
}
