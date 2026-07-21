import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";

type ButtonVariant = "primary" | "secondary" | "destructive" | "ghost";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  loading?: boolean;
  icon?: ReactNode;
};

const variants: Record<ButtonVariant, string> = {
  primary: "border-brand bg-brand text-white hover:bg-teal-800",
  secondary: "border-line bg-panel text-ink hover:bg-slate-100",
  destructive: "border-danger bg-danger text-white hover:bg-red-800",
  ghost: "border-transparent bg-transparent text-ink hover:bg-slate-100"
};

export function Button({ className, variant = "secondary", loading, icon, children, disabled, type = "button", ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex min-h-9 items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-55",
        variants[variant],
        className
      )}
      type={type}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : icon}
      {children}
    </button>
  );
}
