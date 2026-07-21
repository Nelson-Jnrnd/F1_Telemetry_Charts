import type { ButtonHTMLAttributes, ReactNode } from "react";
import * as Tooltip from "@radix-ui/react-tooltip";
import { cn } from "../../lib/utils";

type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
  children: ReactNode;
};

export function IconButton({ label, className, children, ...props }: IconButtonProps) {
  return (
    <Tooltip.Provider delayDuration={250}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <button
            aria-label={label}
            className={cn(
              "inline-flex h-9 w-9 items-center justify-center rounded-md border border-line bg-panel text-ink transition hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-55",
              className
            )}
            {...props}
          >
            {children}
          </button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content className="z-50 rounded bg-ink px-2 py-1 text-xs text-white shadow" sideOffset={6}>
            {label}
            <Tooltip.Arrow className="fill-ink" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}
