import * as RadixTabs from "@radix-ui/react-tabs";
import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

type TabItem<T extends string> = {
  value: T;
  label: string;
};

type TabsProps<T extends string> = {
  value: T;
  items: TabItem<T>[];
  onValueChange: (value: T) => void;
  children: ReactNode;
};

export function Tabs<T extends string>({ value, items, onValueChange, children }: TabsProps<T>) {
  return (
    <RadixTabs.Root value={value} onValueChange={(next) => onValueChange(next as T)}>
      <RadixTabs.List className="mb-4 flex flex-wrap gap-2 border-b border-line">
        {items.map((item) => (
          <RadixTabs.Trigger
            key={item.value}
            value={item.value}
            className={cn(
              "min-h-10 rounded-t-md border border-transparent px-3 text-sm font-medium text-muted outline-none transition hover:bg-slate-100 focus-visible:ring-2 focus-visible:ring-blue-100 data-[state=active]:border-line data-[state=active]:border-b-panel data-[state=active]:bg-panel data-[state=active]:text-ink"
            )}
          >
            {item.label}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
      {children}
    </RadixTabs.Root>
  );
}

export const TabContent = RadixTabs.Content;
