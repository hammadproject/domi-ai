import { X } from "@phosphor-icons/react/ssr";
import type { ReactNode } from "react";

/** Pill chip. With `onRemove` it renders an "x" (active filter); with `onClick` it is a toggle. */
export function Chip({
  children,
  onRemove,
  onClick,
  active = false,
  icon,
  className = "",
}: {
  children: ReactNode;
  onRemove?: () => void;
  onClick?: () => void;
  active?: boolean;
  icon?: ReactNode;
  className?: string;
}) {
  const tone = active || onRemove ? "bg-sage text-sage-ink" : "border border-line bg-surface text-ink-soft";
  const cls = `inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium ${tone} ${className}`;
  if (onClick && !onRemove) {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-pressed={active}
        className={`${cls} transition-colors duration-200 hover:bg-sage active:scale-[0.98]`}
      >
        {icon}
        {children}
      </button>
    );
  }
  return (
    <span className={cls}>
      {icon}
      {children}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Remove ${typeof children === "string" ? children : "filter"}`}
          className="-mr-1 rounded-full p-0.5 hover:bg-sage-strong"
        >
          <X size={12} weight="bold" aria-hidden />
        </button>
      )}
    </span>
  );
}
