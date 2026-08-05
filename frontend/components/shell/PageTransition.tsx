"use client";

import { motion, useReducedMotion, useScroll, useSpring } from "framer-motion";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

/**
 * Reading-progress rail pinned under the header.
 *
 * scaleX with a logical origin means it grows from the start edge of the
 * writing direction — it fills right-to-left under RTL and left-to-right under
 * LTR without a mirrored variant or a direction check in JS.
 */
export function ScrollProgress() {
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 240, damping: 34, restDelta: 0.001 });

  if (reduce) return null;

  return (
    <motion.div
      style={{ scaleX, transformOrigin: "var(--progress-origin, right)" }}
      className="pointer-events-none fixed inset-x-0 top-0 z-50 h-0.5 bg-gradient-to-r from-emerald-500 to-teal-400"
      aria-hidden
    />
  );
}

/**
 * Per-route entrance. Keyed on pathname so the content re-plays its rise on
 * every navigation, which makes route changes feel like movement rather than
 * a hard swap.
 */
export function PageTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const reduce = useReducedMotion();

  if (reduce) return <>{children}</>;

  return (
    <motion.div
      key={pathname}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
