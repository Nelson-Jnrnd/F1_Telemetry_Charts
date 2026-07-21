import * as ToastPrimitive from "@radix-ui/react-toast";
import { cn } from "../../lib/utils";

export type AppToast = {
  id: number;
  title: string;
  description?: string;
  tone?: "success" | "error" | "warning" | "info";
};

type ToastRegionProps = {
  toasts: AppToast[];
  dismiss: (id: number) => void;
};

const toneClasses = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-950",
  error: "border-red-200 bg-red-50 text-red-950",
  warning: "border-amber-200 bg-amber-50 text-amber-950",
  info: "border-blue-200 bg-blue-50 text-blue-950"
};

export function ToastRegion({ toasts, dismiss }: ToastRegionProps) {
  return (
    <ToastPrimitive.Provider swipeDirection="right">
      {toasts.map((toast) => (
        <ToastPrimitive.Root
          key={toast.id}
          open
          duration={4800}
          onOpenChange={(open) => {
            if (!open) dismiss(toast.id);
          }}
          className={cn("grid gap-1 rounded-md border p-3 shadow-lg", toneClasses[toast.tone ?? "info"])}
        >
          <ToastPrimitive.Title className="text-sm font-semibold">{toast.title}</ToastPrimitive.Title>
          {toast.description && <ToastPrimitive.Description className="text-sm">{toast.description}</ToastPrimitive.Description>}
        </ToastPrimitive.Root>
      ))}
      <ToastPrimitive.Viewport className="fixed bottom-4 right-4 z-[60] grid w-[min(380px,calc(100vw-32px))] gap-2 outline-none" />
    </ToastPrimitive.Provider>
  );
}
