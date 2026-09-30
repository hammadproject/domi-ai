"use client";

import { CaretDown } from "@phosphor-icons/react";
import type { ReactNode } from "react";

export interface Option {
  value: string;
  label: string;
}

/**
 * Pill-shaped native <select> (keyboard and screen-reader friendly, and the mobile OS picker
 * comes for free) with a leading icon and our own caret.
 */
export function Select({
  value,
  onChange,
  options,
  label,
  icon,
  className = "",
}: {
  value: string;
  onChange: (value: string) => void;
  options: Option[];
  label: string;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <label
      className={`relative inline-flex h-11 items-center rounded-full border border-line bg-surface text-ink transition-colors focus-within:border-primary hover:bg-sage/60 ${className}`}
    >
      <span className="sr-only">{label}</span>
      {icon && <span className="pointer-events-none absolute left-3.5 text-ink-soft">{icon}</span>}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`h-full w-full cursor-pointer appearance-none rounded-full bg-transparent pr-9 text-sm font-medium outline-none ${icon ? "pl-10" : "pl-4"}`}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <CaretDown size={14} weight="bold" className="pointer-events-none absolute right-3.5 text-ink-soft" aria-hidden />
    </label>
  );
}
