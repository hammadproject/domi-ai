import type { CSSProperties, ElementType, ReactNode } from "react";

/**
 * Entrance motion in pure CSS, so content is always in the server HTML and visible even if
 * scripts are slow or blocked.
 *
 * - default: a short rise-and-fade when the page loads (for content above the fold)
 * - onScroll: the same rise, driven by scroll position as the element enters the viewport
 *   (scroll-driven animations; browsers without support simply show the content)
 *
 * The motion says where the eye should go next. Both are disabled by prefers-reduced-motion.
 */
export function Reveal({
  children,
  delay = 0,
  className = "",
  as: Tag = "div",
  onScroll = false,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: ElementType;
  onScroll?: boolean;
}) {
  return (
    <Tag
      className={`${onScroll ? "rise-on-scroll" : "rise"} ${className}`}
      style={{ "--delay": `${delay}s` } as CSSProperties}
    >
      {children}
    </Tag>
  );
}
