"use client";

import { useEffect } from "react";
import { ErrorState } from "@/components/ui/States";

/** Last-resort boundary for unexpected render errors (request failures are handled in place). */
export default function GlobalRouteError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return <ErrorState error={new Error("An unexpected error stopped this page from loading.")} onRetry={reset} />;
}
