import * as Checkbox from "@radix-ui/react-checkbox";
import { Check } from "lucide-react";
import { cn } from "../../lib/utils";

type CheckboxFieldProps = {
  label: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  description?: string;
  className?: string;
  disabled?: boolean;
};

export function CheckboxField({ label, checked, onCheckedChange, description, className, disabled }: CheckboxFieldProps) {
  return (
    <label className={cn("flex items-start gap-3 rounded-md border border-line bg-panel p-3 text-sm", className)}>
      <Checkbox.Root
        checked={checked}
        disabled={disabled}
        onCheckedChange={(value) => onCheckedChange(value === true)}
        className="mt-0.5 flex h-5 w-5 items-center justify-center rounded border border-line bg-white outline-none focus-visible:ring-2 focus-visible:ring-blue-100 data-[state=checked]:border-brand data-[state=checked]:bg-brand"
      >
        <Checkbox.Indicator>
          <Check className="h-4 w-4 text-white" />
        </Checkbox.Indicator>
      </Checkbox.Root>
      <span className="grid gap-0.5">
        <span className="font-medium text-ink">{label}</span>
        {description && <span className="text-xs leading-5 text-muted">{description}</span>}
      </span>
    </label>
  );
}
