import manifest from "../../public/home-photos/manifest.json";

const POOL: string[] = manifest;

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** A photo from the pool for this listing (stable per id), or null when the pool is empty. */
export function photoFor(id: string): string | null {
  if (POOL.length === 0) return null;
  return `/home-photos/${POOL[hash(id) % POOL.length]}`;
}
