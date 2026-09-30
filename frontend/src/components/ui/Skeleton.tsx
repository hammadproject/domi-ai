/** Shimmer placeholder. Only rendered while a real request is in flight. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`skeleton ${className}`} />;
}

export function ListingCardSkeleton({ variant = "list" }: { variant?: "list" | "grid" }) {
  if (variant === "grid") {
    return (
      <div className="rounded-card border border-line bg-surface p-3" aria-hidden>
        <Skeleton className="h-44 w-full rounded-2xl" />
        <Skeleton className="mt-4 h-7 w-32" />
        <Skeleton className="mt-3 h-4 w-48" />
        <Skeleton className="mt-2 h-4 w-36" />
        <Skeleton className="mt-4 h-11 w-full rounded-full" />
      </div>
    );
  }
  return (
    <div className="flex gap-4 rounded-card border border-line bg-surface p-3" aria-hidden>
      <Skeleton className="h-36 w-40 shrink-0 rounded-2xl sm:w-44" />
      <div className="flex-1 py-1">
        <Skeleton className="h-7 w-28" />
        <Skeleton className="mt-3 h-4 w-44" />
        <Skeleton className="mt-2 h-4 w-32" />
        <Skeleton className="mt-5 h-10 w-full rounded-full" />
      </div>
    </div>
  );
}
