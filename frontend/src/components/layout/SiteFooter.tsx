import Link from "next/link";
import { Logo } from "@/components/ui/Logo";

export function SiteFooter() {
  return (
    <footer className="border-t border-line bg-canvas">
      <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-6 px-4 py-10 sm:px-8 lg:flex-row lg:items-center lg:justify-between">
        <Logo />
        <nav aria-label="Footer" className="flex flex-wrap gap-x-8 gap-y-2 text-[15px] text-ink-soft">
          <Link href="/explore" className="hover:text-ink">Explore</Link>
          <Link href="/compare" className="hover:text-ink">Compare</Link>
          <Link href="/affordability" className="hover:text-ink">Affordability</Link>
        </nav>
        <div className="max-w-md text-sm text-muted lg:text-right">
          <p>Mortgage estimates are illustrative, not loan offers.</p>
          <p className="mt-1">
            Listings via RentCast. Map data &copy;{" "}
            <a
              href="https://www.openstreetmap.org/copyright"
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-2 hover:text-ink"
            >
              OpenStreetMap contributors
            </a>
            . Availability may change.
          </p>
        </div>
      </div>
    </footer>
  );
}
