import type { Metadata } from "next";
import { Suspense } from "react";
import { CompareClient } from "@/components/compare/CompareClient";
import { Skeleton } from "@/components/ui/Skeleton";

export const metadata: Metadata = {
  title: "Compare homes",
  description: "Put two or three homes side by side with shared payment assumptions.",
};

export default function ComparePage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto w-full max-w-[1400px] px-4 pt-8 sm:px-8" aria-busy="true">
          <Skeleton className="h-12 w-96 max-w-full" />
          <Skeleton className="mt-6 h-[420px] w-full rounded-card" />
        </div>
      }
    >
      <CompareClient />
    </Suspense>
  );
}
