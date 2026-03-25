import React from "react";

interface Props {
  x: number;
  y: number;
  scale?: number;
}

// Pot dimensions
const POT_W = 14;
const POT_H = 7;
const POT_DEPTH = 10;

const COLOR_POT_TOP   = "#9B6E4C";
const COLOR_POT_LEFT  = "#7B4E2C";
const COLOR_POT_RIGHT = "#6B3E1C";
const COLOR_LEAF_1    = "#4a8c3f";
const COLOR_LEAF_2    = "#5ea04e";
const COLOR_LEAF_3    = "#3a7a30";
const COLOR_SOIL      = "#2a1a0a";

/**
 * Isometric plant with terracotta pot and layered leaf diamonds.
 * (x, y) is screen-space center of the pot top face.
 */
export function Plant({ x, y, scale = 1 }: Props): React.ReactElement {
  return (
    <g transform={`translate(${x}, ${y}) scale(${scale})`}>
      <IsoPlant />
    </g>
  );
}

function IsoPlant(): React.ReactElement {
  const hw = POT_W / 2;
  const hh = POT_H / 2;

  // Pot top (soil)
  const potTop = `0,${-hh} ${hw},${0} 0,${hh} ${-hw},${0}`;
  // Pot left face
  const potLeft = `${-hw},${0} 0,${hh} 0,${hh + POT_DEPTH} ${-hw},${POT_DEPTH}`;
  // Pot right face
  const potRight = `0,${hh} ${hw},${0} ${hw},${POT_DEPTH} 0,${hh + POT_DEPTH}`;

  // Leaves: stacked diamonds above the pot
  // Each leaf is an isometric diamond at progressively higher Y positions
  const leafOffset = -hh - 6; // just above pot top

  return (
    <g>
      {/* Pot right face */}
      <polygon points={potRight} fill={COLOR_POT_RIGHT} />
      {/* Pot left face */}
      <polygon points={potLeft} fill={COLOR_POT_LEFT} />
      {/* Soil (pot top) */}
      <polygon points={potTop} fill={COLOR_SOIL} />
      {/* Pot top rim */}
      <polygon points={potTop} fill="none" stroke={COLOR_POT_TOP} strokeWidth={1} />

      {/* Leaf cluster — 3 diamond shapes stacked */}
      <LeafDiamond cx={0} cy={leafOffset - 8} rx={8} ry={4} fill={COLOR_LEAF_3} />
      <LeafDiamond cx={-4} cy={leafOffset - 4} rx={7} ry={3.5} fill={COLOR_LEAF_1} />
      <LeafDiamond cx={4} cy={leafOffset - 4} rx={7} ry={3.5} fill={COLOR_LEAF_2} />
      <LeafDiamond cx={0} cy={leafOffset} rx={9} ry={4.5} fill={COLOR_LEAF_1} />
    </g>
  );
}

function LeafDiamond({
  cx, cy, rx, ry, fill,
}: {
  cx: number; cy: number; rx: number; ry: number; fill: string;
}): React.ReactElement {
  const pts = `${cx},${cy - ry} ${cx + rx},${cy} ${cx},${cy + ry} ${cx - rx},${cy}`;
  return (
    <polygon
      points={pts}
      fill={fill}
      stroke="#1a3a14"
      strokeWidth={0.4}
    />
  );
}
