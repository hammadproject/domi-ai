import type { Metadata } from "next";
import { Suspense } from "react";
import { AffordClient } from "@/components/afford/AffordClient";
import { Skeleton } from "@/components/ui/Skeleton";

export const metadata: Metadata = {
  title: "Affordability",
  description: "Estimate monthly payments and what you may be able to afford, with editable assumptions.",
};

export default function AffordabilityPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto w-full max-w-[1400px] px-4 pt-8 sm:px-8" aria-busy="true">
          <Skeleton className="h-12 w-96 max-w-full" />
          <Skeleton className="mt-8 h-[520px] w-full rounded-card" />
        </div>
      }
    >
      <AffordClient />
    </Suspense>
  );
}
