"use client";

import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { CaretDown, Check } from "@phosphor-icons/react";

export interface Option {
  value: string;
  label: string;
}

interface Pos {
  left: number;
  minWidth: number;
  top?: number;
  bottom?: number;
  maxHeight: number;
}

/**
 * A styled dropdown (the browser's own <select> menu cannot be themed). A button opens a
 * rounded menu that is rendered in a portal, so it is never clipped by a scrolling panel.
 * Keyboard: Arrow keys / Home / End move, Enter or Space picks, Escape and Tab close.
 *
 * variant "pill" is for filter bars; "field" is a full-width form field.
 */
export function Select({
  value,
  onChange,
  options,
  label,
  icon,
  className = "",
  variant = "pill",
  size = "md",
}: {
  value: string;
  onChange: (value: string) => void;
  options: Option[];
  label: string;
  icon?: ReactNode;
  className?: string;
  variant?: "pill" | "field";
  size?: "md" | "sm";
}) {
  const uid = useId();
  const listId = `${uid}-list`;
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [pos, setPos] = useState<Pos | null>(null);

  const selectedIndex = Math.max(
    0,
    options.findIndex((o) => o.value === value),
  );
  const selected = options[selectedIndex];

  const openMenu = () => {
    const r = buttonRef.current?.getBoundingClientRect();
    if (!r) return;
    const below = window.innerHeight - r.bottom - 12;
    const above = r.top - 12;
    const flip = below < 240 && above > below; // open upward when there is more room above
    setPos(
      flip
        ? { left: r.left, minWidth: r.width, bottom: window.innerHeight - r.top + 6, maxHeight: Math.min(340, above) }
        : { left: r.left, minWidth: r.width, top: r.bottom + 6, maxHeight: Math.min(340, below) },
    );
    setActive(selectedIndex);
    setOpen(true);
  };

  const choose = (i: number) => {
    onChange(options[i].value);
    setOpen(false);
    buttonRef.current?.focus();
  };

  const close = useCallback(() => setOpen(false), []);

  // close on outside click, page scroll, resize
  useEffect(() => {
    if (!open) return;
    const inside = (t: EventTarget | null) =>
      Boolean(t instanceof Node && (buttonRef.current?.contains(t) || document.getElementById(listId)?.contains(t)));
    const onDown = (e: PointerEvent) => !inside(e.target) && close();
    const onScroll = (e: Event) => !inside(e.target) && close();
    document.addEventListener("pointerdown", onDown);
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", close);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", close);
    };
  }, [open, listId, close]);

  // keep the highlighted option visible
  useEffect(() => {
    if (open) document.getElementById(`${uid}-opt-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [open, active, uid]);

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    switch (e.key) {
      case "ArrowDown":
      case "ArrowUp": {
        e.preventDefault();
        if (!open) return openMenu();
        const step = e.key === "ArrowDown" ? 1 : -1;
        setActive((i) => (i + step + options.length) % options.length);
        break;
      }
      case "Home":
      case "End":
        if (open) {
          e.preventDefault();
          setActive(e.key === "Home" ? 0 : options.length - 1);
        }
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        if (open) choose(active);
        else openMenu();
        break;
      case "Escape":
        if (open) {
          e.preventDefault();
          close();
        }
        break;
      case "Tab":
        close();
        break;
    }
  };

  const sizes =
    variant === "field"
      ? "h-10 w-full justify-between rounded-xl bg-canvas px-3 text-[14px]"
      : size === "sm"
        ? "h-9 rounded-full bg-surface px-3 text-[12.5px]"
        : "h-11 rounded-full bg-surface px-4 text-sm";

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open ? `${uid}-opt-${active}` : undefined}
        aria-label={`${label}: ${selected?.label ?? ""}`}
        onClick={() => (open ? close() : openMenu())}
        onKeyDown={onKeyDown}
        className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap border font-medium text-ink transition-[background-color,border-color,box-shadow] duration-200 ${
          open ? "border-primary bg-sage/60 shadow-[0_0_0_3px_color-mix(in_srgb,var(--primary)_14%,transparent)]" : "border-line hover:bg-sage/60"
        } ${sizes} ${className}`}
      >
        {icon && <span className="text-ink-soft [&>svg]:size-4">{icon}</span>}
        <span className="truncate">{selected?.label}</span>
        <CaretDown size={12} weight="bold" className={`shrink-0 text-ink-soft transition-transform duration-200 ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>

      {open &&
        pos &&
        createPortal(
          <ul
            id={listId}
            role="listbox"
            aria-label={label}
            style={{ position: "fixed", left: pos.left, top: pos.top, bottom: pos.bottom, minWidth: Math.max(pos.minWidth, 168), maxHeight: pos.maxHeight }}
            className="z-[80] overflow-y-auto rounded-2xl border border-line bg-surface p-1.5 shadow-lift"
          >
            {options.map((o, i) => {
              const isSelected = i === selectedIndex;
              return (
                <li
                  key={o.value}
                  id={`${uid}-opt-${i}`}
                  role="option"
                  aria-selected={isSelected}
                  onPointerEnter={() => setActive(i)}
                  onPointerDown={(e) => e.preventDefault()} // keep focus on the button
                  onClick={() => choose(i)}
                  className={`flex cursor-pointer items-center justify-between gap-6 rounded-xl px-3 py-2 text-sm ${
                    i === active ? "bg-sage text-ink" : "text-ink-soft"
                  } ${isSelected ? "font-semibold text-ink" : ""}`}
                >
                  <span className="whitespace-nowrap">{o.label}</span>
                  {isSelected && <Check size={14} weight="bold" className="shrink-0 text-sage-ink" aria-hidden />}
                </li>
              );
            })}
          </ul>,
          document.body,
        )}
    </>
  );
}
