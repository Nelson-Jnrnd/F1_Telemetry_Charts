import { cn } from "../../lib/utils";

const toneClasses = {
  healthy: "border-emerald-200 bg-emerald-50 text-emerald-800",
  valid: "border-emerald-200 bg-emerald-50 text-emerald-800",
  saved: "border-emerald-200 bg-emerald-50 text-emerald-800",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
  invalid: "border-red-200 bg-red-50 text-red-800",
  unhealthy: "border-red-200 bg-red-50 text-red-800",
  info: "border-blue-200 bg-blue-50 text-blue-800",
  neutral: "border-line bg-slate-50 text-slate-700"
};

export function StatusBadge({ value, className }: { value?: string | null; className?: string }) {
  const key = value && value in toneClasses ? (value as keyof typeof toneClasses) : "neutral";
  return (
    <span className={cn("inline-flex h-7 items-center rounded-full border px-2.5 text-xs font-semibold capitalize", toneClasses[key], className)}>
      {value ?? "none"}
    </span>
  );
}
