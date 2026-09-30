import { HouseLine, MagnifyingGlass, WifiSlash, Warning } from "@phosphor-icons/react/ssr";
import type { ReactNode } from "react";
import { ApiError } from "@/lib/api";

function IconCircle({ children, tone = "sage" }: { children: ReactNode; tone?: "sage" | "danger" }) {
  return (
    <span
      className={`grid size-16 place-items-center rounded-full ${tone === "sage" ? "bg-sage text-sage-ink" : "bg-danger-bg text-danger"}`}
    >
      {children}
    </span>
  );
}

/** Nothing matched. Always offers a way forward (edit filters / reset). */
export function EmptyState({
  title,
  body,
  actions,
  compact = false,
}: {
  title: string;
  body: string;
  actions?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div
      role="status"
      className={`mx-auto flex max-w-md flex-col items-center text-center ${compact ? "py-10" : "py-20"}`}
    >
      <IconCircle>
        <MagnifyingGlass size={28} aria-hidden />
      </IconCircle>
      <h2 className="font-display mt-5 text-3xl font-bold text-ink">{title}</h2>
      <p className="mt-2 text-ink-soft">{body}</p>
      {actions && <div className="mt-6 flex w-full flex-col gap-3 sm:flex-row sm:justify-center">{actions}</div>}
    </div>
  );
}

/** A real failed request: says what happened and retries the same request. */
export function ErrorState({
  error,
  onRetry,
  title,
  compact = false,
}: {
  error: ApiError | Error | null | undefined;
  onRetry?: () => void;
  title?: string;
  compact?: boolean;
}) {
  const api = error instanceof ApiError ? error : null;
  const offline = api?.isNetwork ?? false;
  return (
    <div
      role="alert"
      className={`mx-auto flex max-w-md flex-col items-center text-center ${compact ? "py-10" : "py-20"}`}
    >
      <IconCircle tone="danger">
        {offline ? <WifiSlash size={28} aria-hidden /> : <Warning size={28} aria-hidden />}
      </IconCircle>
      <h2 className="font-display mt-5 text-3xl font-bold text-ink">
        {title ?? (offline ? "Domi can't be reached" : "Something went wrong")}
      </h2>
      <p className="mt-2 text-ink-soft">{api ? api.friendly : (error?.message ?? "Please try again.")}</p>
      {api?.requestId && (
        <p className="mt-2 text-xs text-muted">Reference: {api.requestId}</p>
      )}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-6 inline-flex h-11 items-center justify-center rounded-full bg-primary px-6 text-sm font-medium text-on-primary transition-[background-color,transform] hover:bg-primary-hover active:scale-[0.98]"
        >
          Try again
        </button>
      )}
    </div>
  );
}

export function PageLoading({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="grid place-items-center py-24 text-muted">
      <HouseLine size={32} aria-hidden className="mb-3" />
      <span className="text-sm">{label}</span>
    </div>
  );
}
