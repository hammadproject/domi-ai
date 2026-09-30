"use client";

import { useReducedMotion } from "motion/react";

/**
 * True when interactive (Motion) animations should be skipped: the visitor prefers reduced
 * motion, or NEXT_PUBLIC_DISABLE_MOTION=1 is set. The flag exists for automated browser
 * checks, where background windows never run requestAnimationFrame.
 */
export function useNoMotion(): boolean {
  const reduce = useReducedMotion();
  return Boolean(reduce) || process.env.NEXT_PUBLIC_DISABLE_MOTION === "1";
}
