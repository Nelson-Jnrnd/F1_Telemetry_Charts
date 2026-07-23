import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

type FieldShellProps = {
  label: string;
  description?: string;
  error?: string;
  children: ReactNode;
  className?: string;
};

export function FieldShell({ label, description, error, children, className }: FieldShellProps) {
  return (
    <label className={cn("grid min-w-0 gap-1.5 text-sm", className)}>
      <span className="font-medium text-ink">{label}</span>
      {children}
      {description && <span className="text-xs leading-5 text-muted">{description}</span>}
      {error && <span className="text-xs font-medium text-danger">{error}</span>}
    </label>
  );
}

type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  description?: string;
  error?: string;
};

export function Field({ label, description, error, className, ...props }: FieldProps) {
  return (
    <FieldShell label={label} description={description} error={error}>
      <input
        className={cn(
          "h-10 w-full min-w-0 rounded-md border border-line bg-panel px-3 text-sm text-ink outline-none transition placeholder:text-slate-400 focus:border-accent focus:ring-2 focus:ring-blue-100",
          error && "border-danger focus:border-danger focus:ring-red-100",
          className
        )}
        {...props}
      />
    </FieldShell>
  );
}

type TextAreaFieldProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
  description?: string;
  error?: string;
};

export function TextAreaField({ label, description, error, className, ...props }: TextAreaFieldProps) {
  return (
    <FieldShell label={label} description={description} error={error}>
      <textarea
        className={cn(
          "min-h-28 w-full min-w-0 rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink outline-none transition placeholder:text-slate-400 focus:border-accent focus:ring-2 focus:ring-blue-100",
          error && "border-danger focus:border-danger focus:ring-red-100",
          className
        )}
        {...props}
      />
    </FieldShell>
  );
}
