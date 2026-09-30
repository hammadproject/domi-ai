"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, ArrowUpRight, List, X } from "@phosphor-icons/react";
import { Logo } from "@/components/ui/Logo";
import { LinkButton } from "@/components/ui/Button";
import { useCompare } from "@/state/compare";

const NAV = [
  { href: "/explore", label: "Explore" },
  { href: "/compare", label: "Compare" },
  { href: "/affordability", label: "Affordability" },
] as const;

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const { items } = useCompare();
  const onLanding = pathname === "/";

  const isActive = (href: string) =>
    pathname === href || (href === "/explore" && pathname.startsWith("/listings"));

  return (
    <header className="sticky top-0 z-[var(--z-header,40)] border-b border-line/70 bg-canvas">
      <div className="mx-auto flex h-[68px] w-full max-w-[1400px] items-center justify-between px-4 sm:px-8">
        <Logo />

        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
          {NAV.map((item) => {
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`relative rounded-full px-4 py-2 text-[15px] font-medium transition-colors ${
                  active ? "bg-sage text-ink" : "text-ink-soft hover:bg-sage/60 hover:text-ink"
                }`}
              >
                {item.label}
                {item.href === "/compare" && items.length > 0 && (
                  <span className="ml-1.5 inline-grid size-5 place-items-center rounded-full bg-primary text-[11px] font-semibold text-on-primary">
                    {items.length}
                  </span>
                )}
                {active && (
                  <span className="absolute inset-x-4 -bottom-[13px] h-0.5 rounded-full bg-primary" />
                )}
              </Link>
            );
          })}
        </nav>

        <div className="hidden md:block">
          {onLanding ? (
            <LinkButton href="/explore">
              Explore homes <ArrowUpRight size={16} weight="bold" aria-hidden />
            </LinkButton>
          ) : (
            <Link
              href="/"
              className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-[15px] font-medium text-ink-soft transition-colors hover:bg-sage/60 hover:text-ink"
            >
              <ArrowLeft size={16} aria-hidden /> Back to home
            </Link>
          )}
        </div>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-controls="mobile-menu"
          aria-label={open ? "Close menu" : "Open menu"}
          className="grid size-11 place-items-center rounded-full text-ink hover:bg-sage md:hidden"
        >
          {open ? <X size={24} aria-hidden /> : <List size={24} aria-hidden />}
        </button>
      </div>

      {open && (
        <nav
          id="mobile-menu"
          aria-label="Mobile"
          className="border-t border-line bg-canvas px-4 pb-5 pt-3 md:hidden"
        >
          <ul className="flex flex-col gap-1">
            {NAV.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={() => setOpen(false)}
                  aria-current={isActive(item.href) ? "page" : undefined}
                  className={`flex items-center justify-between rounded-2xl px-4 py-3 text-base font-medium ${
                    isActive(item.href) ? "bg-sage text-ink" : "text-ink-soft"
                  }`}
                >
                  {item.label}
                  {item.href === "/compare" && items.length > 0 && (
                    <span className="grid size-6 place-items-center rounded-full bg-primary text-xs font-semibold text-on-primary">
                      {items.length}
                    </span>
                  )}
                </Link>
              </li>
            ))}
            <li className="pt-2">
              <LinkButton href={onLanding ? "/explore" : "/"} variant={onLanding ? "primary" : "secondary"} className="w-full" onClick={() => setOpen(false)}>
                {onLanding ? "Explore homes" : "Back to home"}
              </LinkButton>
            </li>
          </ul>
        </nav>
      )}
    </header>
  );
}
