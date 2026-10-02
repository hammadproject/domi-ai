import Link from "next/link";
import { Info } from "@phosphor-icons/react/ssr";
import { Logo } from "@/components/ui/Logo";

const GROUPS = [
  {
    title: "Browse",
    links: [
      { href: "/explore", label: "Explore homes" },
      { href: "/compare", label: "Compare" },
      { href: "/affordability", label: "Affordability" },
    ],
  },
  {
    title: "Cities",
    links: [
      { href: "/explore?city=Austin", label: "Austin, TX" },
      { href: "/explore?city=Dallas", label: "Dallas, TX" },
      { href: "/explore?city=Phoenix", label: "Phoenix, AZ" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="mt-8 border-t border-line bg-surface-2/60">
      <div className="mx-auto w-full max-w-[1400px] px-4 pb-6 pt-10 sm:px-8">
        <div className="grid grid-cols-1 gap-10 md:grid-cols-[minmax(0,1.4fr)_repeat(2,minmax(0,0.7fr))_minmax(0,1.3fr)]">
          <div>
            <Logo />
            <p className="mt-3 max-w-[32ch] text-[14px] leading-relaxed text-ink-soft">
              A calmer way to search for a home in Austin, Dallas and Phoenix.
            </p>
          </div>

          {GROUPS.map((g) => (
            <nav key={g.title} aria-label={g.title}>
              <h2 className="font-display text-lg font-bold text-ink">{g.title}</h2>
              <ul className="mt-3 space-y-2">
                {g.links.map((l) => (
                  <li key={l.href}>
                    <Link href={l.href} className="text-[14px] text-ink-soft transition-colors hover:text-ink">
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}

          <div className="rounded-2xl border border-line bg-surface p-4">
            <p className="flex items-center gap-2 text-sm font-semibold text-ink">
              <Info size={16} className="text-sage-ink" aria-hidden /> Good to know
            </p>
            <p className="mt-2 text-sm leading-relaxed text-ink-soft">
              Mortgage estimates are illustrative, not loan offers. Listing details and availability may change.
            </p>
          </div>
        </div>

        <div className="mt-8 flex flex-col gap-2 border-t border-line pt-5 text-[12.5px] text-muted sm:flex-row sm:items-center sm:justify-between">
          <p>&copy; {new Date().getFullYear()} Domi. Listings via RentCast.</p>
          <p>
            Map data &copy;{" "}
            <a
              href="https://www.openstreetmap.org/copyright"
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-2 hover:text-ink"
            >
              OpenStreetMap contributors
            </a>
            .
          </p>
        </div>
      </div>
    </footer>
  );
}
