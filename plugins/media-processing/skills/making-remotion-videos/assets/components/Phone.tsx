import React from "react";
import { AbsoluteFill } from "remotion";
// Self-contained: set VIEW to the captured device's CSS viewport and the
// colours to the app's. Captures should be VIEW.w * dpr wide.
export const VIEW = { w: 390, h: 844 }; // iPhone 14/15 screen in CSS px
const C = { bezel: "#15120D", bg: "#FFFFFF", statusBg: "#000000", statusFg: "#FFFFFF" };
const F = { sans: "system-ui, sans-serif" };

export const SCREEN_W = 700;
export const K = SCREEN_W / VIEW.w; // display px per CSS px
export const STATUS_H = 50;
export const SCREEN_H = Math.round(VIEW.h * K) + STATUS_H;
const BEZEL = 20;
export const PHONE_W = SCREEN_W + BEZEL * 2;
export const PHONE_H = SCREEN_H + BEZEL * 2;

// A generic modern phone: bezel, status bar, island, home indicator.
// The status bar takes the colour of the app's header so it reads as one surface.
export const Phone: React.FC<{ statusBg?: string; statusFg?: string; children: React.ReactNode }> = ({
  statusBg = C.statusBg,
  statusFg = C.statusFg,
  children,
}) => (
  <div
    style={{
      width: PHONE_W,
      height: PHONE_H,
      borderRadius: 104,
      background: C.bezel,
      padding: BEZEL,
      boxShadow: "0 60px 120px rgba(60,35,15,0.35), 0 20px 40px rgba(60,35,15,0.25), inset 0 0 0 3px #3a332a",
      position: "relative",
    }}
  >
    <div style={{ width: SCREEN_W, height: SCREEN_H, borderRadius: 86, overflow: "hidden", position: "relative", background: C.bg }}>
      <div style={{ position: "absolute", top: STATUS_H, left: 0, width: SCREEN_W, height: SCREEN_H - STATUS_H, overflow: "hidden" }}>
        {children}
      </div>
      <div
        style={{
          position: "absolute", top: 0, left: 0, width: SCREEN_W, height: STATUS_H, background: statusBg, color: statusFg,
          display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 56px 0",
          fontFamily: F.sans, fontWeight: 700, fontSize: 24, boxSizing: "border-box",
        }}
      >
        <span>9:41</span>
        <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Bars color={statusFg} />
          <span style={{ width: 38, height: 18, borderRadius: 5, border: `2px solid ${statusFg}`, position: "relative", opacity: 0.9 }}>
            <span style={{ position: "absolute", inset: 2, right: 8, background: statusFg, borderRadius: 2 }} />
          </span>
        </span>
      </div>
      <div style={{ position: "absolute", top: 12, left: SCREEN_W / 2 - 90, width: 180, height: 40, borderRadius: 20, background: "#000" }} />
      <div style={{ position: "absolute", bottom: 12, left: SCREEN_W / 2 - 110, width: 220, height: 7, borderRadius: 4, background: "rgba(26,22,16,0.55)" }} />
    </div>
  </div>
);

const Bars: React.FC<{ color: string }> = ({ color }) => (
  <span style={{ display: "flex", gap: 3, alignItems: "flex-end", height: 18 }}>
    {[7, 10, 13, 17].map((h) => (
      <span key={h} style={{ width: 5, height: h, background: color, borderRadius: 1 }} />
    ))}
  </span>
);

// Fill the screen area; use inside <Phone>.
export const Screen: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill style={{ overflow: "hidden" }}>{children}</AbsoluteFill>
);
