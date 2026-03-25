// ---------------------------------------------------------------------------
// Isometric projection utilities
// ---------------------------------------------------------------------------

// Tile dimensions: 88px wide, 44px tall (~37% more space between elements)
export const TILE_W = 88;
export const TILE_H = 44;

/**
 * Convert a grid (col, row) coordinate to screen (x, y) in isometric projection.
 * Origin is the top-center diamond of the grid.
 */
export function toIso(col: number, row: number): { x: number; y: number } {
  return {
    x: (col - row) * (TILE_W / 2),
    y: (col + row) * (TILE_H / 2),
  };
}

/**
 * Diamond tile polygon point string for SVG <polygon points="...">.
 * Tile origin is the top vertex of the diamond.
 */
export function tilePath(col: number, row: number): string {
  const { x, y } = toIso(col, row);
  const hw = TILE_W / 2;
  const hh = TILE_H / 2;
  // top, right, bottom, left vertices
  return `${x},${y} ${x + hw},${y + hh} ${x},${y + TILE_H} ${x - hw},${y + hh}`;
}

/**
 * Z-sort key: higher col+row = rendered later (closer to viewer).
 */
export function zOrder(col: number, row: number): number {
  return col + row;
}

/**
 * Screen center pixel for a tile — useful for placing items on top of a tile.
 * Returns the center of the tile surface.
 */
export function tileCenter(col: number, row: number): { x: number; y: number } {
  const { x, y } = toIso(col, row);
  return { x, y: y + TILE_H / 2 };
}
