import * as Select from "@radix-ui/react-select";
import { ChevronDown, Check } from "lucide-react";
import { cn } from "../../lib/utils";

type SelectFieldProps = {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onValueChange: (value: string) => void;
  description?: string;
  error?: string;
  className?: string;
  disabled?: boolean;
};

export function SelectField({ label, value, options, onValueChange, description, error, className, disabled }: SelectFieldProps) {
  return (
    <label className={cn("grid gap-1.5 text-sm", className)}>
      <span className="font-medium text-ink">{label}</span>
      <Select.Root value={value} onValueChange={onValueChange} disabled={disabled}>
        <Select.Trigger
          className={cn(
            "inline-flex h-10 items-center justify-between gap-2 rounded-md border border-line bg-panel px-3 text-left text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-blue-100",
            disabled && "cursor-not-allowed opacity-60",
            error && "border-danger focus:border-danger focus:ring-red-100"
          )}
        >
          <Select.Value />
          <Select.Icon>
            <ChevronDown className="h-4 w-4" />
          </Select.Icon>
        </Select.Trigger>
        <Select.Portal>
          <Select.Content className="z-50 overflow-hidden rounded-md border border-line bg-panel shadow-overlay">
            <Select.Viewport className="p-1">
              {options.map((option) => (
                <Select.Item
                  key={option.value}
                  value={option.value}
                  className="relative flex h-9 cursor-default select-none items-center rounded px-8 text-sm text-ink outline-none data-[highlighted]:bg-slate-100"
                >
                  <Select.ItemIndicator className="absolute left-2">
                    <Check className="h-4 w-4" />
                  </Select.ItemIndicator>
                  <Select.ItemText>{option.label}</Select.ItemText>
                </Select.Item>
              ))}
            </Select.Viewport>
          </Select.Content>
        </Select.Portal>
      </Select.Root>
      {description && <span className="text-xs leading-5 text-muted">{description}</span>}
      {error && <span className="text-xs font-medium text-danger">{error}</span>}
    </label>
  );
}
