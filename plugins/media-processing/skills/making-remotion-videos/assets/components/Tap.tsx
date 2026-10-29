import React from "react";
import { interpolate, useCurrentFrame } from "remotion";

// A touch indicator: finger-down dot, then a ring that expands and fades.
export const Tap: React.FC<{ x: number; y: number; at: number }> = ({ x, y, at }) => {
  const f = useCurrentFrame() - at;
  if (f < 0 || f > 22) return null;
  const dot = interpolate(f, [0, 4, 10, 16], [0, 1, 1, 0], { extrapolateRight: "clamp" });
  const ring = interpolate(f, [4, 22], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <>
      <div style={{ position: "absolute", left: x - 36, top: y - 36, width: 72, height: 72, borderRadius: 36, background: "rgba(255,255,255,0.55)", border: "3px solid rgba(26,22,16,0.35)", opacity: dot, transform: `scale(${0.8 + 0.2 * dot})` }} />
      <div style={{ position: "absolute", left: x - 36, top: y - 36, width: 72, height: 72, borderRadius: 36, border: "4px solid rgba(184,90,40,0.8)", opacity: 1 - ring, transform: `scale(${1 + ring * 1.6})` }} />
    </>
  );
};
