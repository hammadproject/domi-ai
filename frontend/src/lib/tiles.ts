// OpenStreetMap slippy-map tile math, so cards can show a real map of each listing's
// location (the listing data has no photos) without one Leaflet instance per card.

const TILE = 256;

export function worldPixel(lat: number, lng: number, zoom: number) {
  const scale = TILE * 2 ** zoom;
  const x = ((lng + 180) / 360) * scale;
  const sin = Math.sin((lat * Math.PI) / 180);
  const y = (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * scale;
  return { x, y };
}

export interface PlacedTile {
  key: string;
  url: string;
  /** offset of the tile's top-left corner from the map centre, in CSS pixels */
  dx: number;
  dy: number;
}

/** Tiles needed to fill a (maxW x maxH) box centred on lat/lng. */
export function tilesAround(
  lat: number,
  lng: number,
  zoom: number,
  maxW: number,
  maxH: number,
): PlacedTile[] {
  const c = worldPixel(lat, lng, zoom);
  const n = 2 ** zoom;
  const x0 = Math.floor((c.x - maxW / 2) / TILE);
  const x1 = Math.floor((c.x + maxW / 2) / TILE);
  const y0 = Math.max(0, Math.floor((c.y - maxH / 2) / TILE));
  const y1 = Math.min(n - 1, Math.floor((c.y + maxH / 2) / TILE));
  const out: PlacedTile[] = [];
  for (let ty = y0; ty <= y1; ty++) {
    for (let tx = x0; tx <= x1; tx++) {
      const wrapped = ((tx % n) + n) % n;
      out.push({
        key: `${zoom}/${tx}/${ty}`,
        url: `https://tile.openstreetmap.org/${zoom}/${wrapped}/${ty}.png`,
        dx: tx * TILE - c.x,
        dy: ty * TILE - c.y,
      });
    }
  }
  return out;
}

/** Pixel offset of a point from the map centre. */
export function offsetFromCenter(
  center: { lat: number; lng: number },
  point: { lat: number; lng: number },
  zoom: number,
) {
  const c = worldPixel(center.lat, center.lng, zoom);
  const p = worldPixel(point.lat, point.lng, zoom);
  return { dx: p.x - c.x, dy: p.y - c.y };
}
