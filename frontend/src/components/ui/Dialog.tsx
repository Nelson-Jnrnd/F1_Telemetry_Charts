import * as DialogPrimitive from "@radix-ui/react-dialog";
import type { ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "../../lib/utils";
import { IconButton } from "./IconButton";

type DialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
  hideCloseButton?: boolean;
};

export function Dialog({ open, onOpenChange, title, description, children, className, hideCloseButton }: DialogProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-slate-950/55" />
        <DialogPrimitive.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 grid max-h-[calc(100vh-48px)] w-[min(760px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 gap-4 overflow-auto rounded-lg border border-line bg-panel p-5 shadow-overlay focus:outline-none",
            className
          )}
        >
          <header className={cn("grid gap-1", !hideCloseButton && "pr-10")}>
            <DialogPrimitive.Title className="text-lg font-semibold text-ink">{title}</DialogPrimitive.Title>
            {description && <DialogPrimitive.Description className="text-sm text-muted">{description}</DialogPrimitive.Description>}
          </header>
          {!hideCloseButton && (
            <DialogPrimitive.Close asChild>
              <IconButton label="Close" className="absolute right-4 top-4">
                <X className="h-4 w-4" />
              </IconButton>
            </DialogPrimitive.Close>
          )}
          {children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
