"use client";
import { useEffect, useRef, useState } from "react";

/** Animates a number counting up to `target` on mount/change — a friendly
 * motion cue for KPI tiles read by business users, not a raw static digit. */
export function useCountUp(target: number, duration = 900): number {
  const [value, setValue] = useState(0);
  const frame = useRef<number>();

  useEffect(() => {
    const start = performance.now();
    frame.current = requestAnimationFrame(function tick(now: number) {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out-cubic
      setValue(target * eased);
      if (t < 1) frame.current = requestAnimationFrame(tick);
    });
    return () => {
      if (frame.current) cancelAnimationFrame(frame.current);
    };
  }, [target, duration]);

  return value;
}
