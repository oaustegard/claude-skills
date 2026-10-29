import React from "react";
import { Img, interpolate, staticFile, useCurrentFrame, Easing } from "remotion";
import { K, SCREEN_W } from "./Phone";

export type Key = { f: number; y: number }; // frame -> scroll offset in CSS px

// A full-page capture shown through the phone screen. `keys` scroll it; an
// optional sticky header (top `stickyH` CSS px of the same capture) stays put,
// as the app's own header does.
export const ScrollShot: React.FC<{ src: string; keys: Key[]; stickyH?: number; children?: React.ReactNode }> = ({
  src,
  keys,
  stickyH = 0,
  children,
}) => {
  const frame = useCurrentFrame();
  const y =
    keys.length === 1
      ? keys[0].y
      : interpolate(frame, keys.map((k) => k.f), keys.map((k) => k.y), {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.inOut(Easing.cubic),
        });
  return (
    <>
      <Img src={staticFile(src)} style={{ position: "absolute", left: 0, top: -y * K, width: SCREEN_W }} />
      {children}
      {stickyH > 0 && (
        <div style={{ position: "absolute", left: 0, top: 0, width: SCREEN_W, height: stickyH * K, overflow: "hidden", boxShadow: y > 4 ? "0 4px 14px rgba(0,0,0,0.18)" : "none" }}>
          <Img src={staticFile(src)} style={{ position: "absolute", left: 0, top: 0, width: SCREEN_W }} />
        </div>
      )}
    </>
  );
};

// Scroll position at a frame, for overlays that track page content.
export const scrollAt = (frame: number, keys: Key[]) =>
  keys.length === 1
    ? keys[0].y
    : interpolate(frame, keys.map((k) => k.f), keys.map((k) => k.y), {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.inOut(Easing.cubic),
      });
