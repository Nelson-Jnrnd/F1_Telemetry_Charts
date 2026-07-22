import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function compactPath(value?: string | null) {
  if (!value) return "None";
  const normalized = value.replaceAll("\\", "/");
  const parts = normalized.split("/");
  return parts.length > 4 ? `.../${parts.slice(-4).join("/")}` : value;
}
