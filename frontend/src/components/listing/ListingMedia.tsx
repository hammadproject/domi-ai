import { TileMap, pinKindOf } from "@/components/map/TileMap";
import { photoFor } from "@/lib/photos";
import type { Listing } from "@/lib/types";

/**
 * The picture for a listing card: a photo from the pool when one is configured, otherwise a
 * real map of the home. The map is zoomed closer for buildings (condos, multi-family) than for
 * houses, so neighbouring listings read differently.
 */
export function ListingMedia({
  listing: l,
  maxW,
  maxH,
  className = "",
}: {
  listing: Pick<Listing, "id" | "address" | "lat" | "lng" | "property_type">;
  maxW: number;
  maxH: number;
  className?: string;
}) {
  const photo = photoFor(l.id);
  if (photo) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- local pool image, sized by the box
      <img src={photo} alt="" loading="lazy" decoding="async" className={`object-cover ${className}`} />
    );
  }
  const kind = pinKindOf(l.property_type);
  return (
    <TileMap
      lat={l.lat}
      lng={l.lng}
      zoom={kind === "building" ? 19 : kind === "land" ? 16 : 18}
      maxW={maxW}
      maxH={maxH}
      centerPin
      pinKind={kind}
      className={className}
    />
  );
}
