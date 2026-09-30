import type { Metadata } from "next";
import { Suspense } from "react";
import { ExploreClient } from "@/components/explore/ExploreClient";
import { ListingCardSkeleton, Skeleton } from "@/components/ui/Skeleton";

export const metadata: Metadata = {
  title: "Explore homes",
  description: "Filter homes in Austin, Dallas and Phoenix, see them on a map, and ask Domi.",
};

function ExploreFallback() {
  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 pt-8 sm:px-8" aria-busy="true">
      <Skeleton className="h-12 w-80 max-w-full" />
      <Skeleton className="mt-4 h-5 w-64" />
      <div className="mt-6 flex gap-2.5">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-11 w-36 rounded-full" />
        ))}
      </div>
      <div className="mt-8 grid gap-4 lg:grid-cols-3">
        <ListingCardSkeleton />
        <ListingCardSkeleton />
        <ListingCardSkeleton />
      </div>
    </div>
  );
}

export default function ExplorePage() {
  return (
    <Suspense fallback={<ExploreFallback />}>
      <ExploreClient />
    </Suspense>
  );
}
