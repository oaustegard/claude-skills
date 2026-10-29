import React from "react";
import { Img, staticFile, useCurrentFrame } from "remotion";
import { SCREEN_W } from "./Phone";

// Plays a captured frame directory (f0000.jpg ...) one capture per output frame.
export const FrameSequence: React.FC<{ dir: string; count: number; offset?: number }> = ({ dir, count, offset = 0 }) => {
  const frame = useCurrentFrame();
  const i = Math.max(0, Math.min(count - 1, frame + offset));
  return <Img src={staticFile(`${dir}/f${String(i).padStart(4, "0")}.jpg`)} style={{ position: "absolute", left: 0, top: 0, width: SCREEN_W }} />;
};
