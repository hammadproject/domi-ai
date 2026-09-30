import Link from "next/link";
import { HouseLine } from "@phosphor-icons/react/ssr";

export function Logo({ className = "" }: { className?: string }) {
  return (
    <Link
      href="/"
      aria-label="Domi home"
      className={`inline-flex items-center gap-2 text-primary ${className}`}
    >
      <HouseLine size={30} weight="regular" aria-hidden />
      <span className="font-display text-[28px] font-bold lowercase leading-none tracking-tight">
        domi
      </span>
    </Link>
  );
}
