"use client";

import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

type Props = {
  children: React.ReactNode;
  className?: string;
  /** Stagger index — children of a `.stagger` group cascade by --stagger-step. */
  index?: number;
  /** Fraction of the element that must be visible before it reveals. */
  threshold?: number;
  as?: "div" | "section" | "article" | "li";
};

/**
 * Reveals its children once they scroll into view.
 *
 * The element starts visible in CSS and is only hidden inside a
 * `prefers-reduced-motion: no-preference` block, so a reader with reduced
 * motion — or a failed/unsupported observer — always sees the content.
 */
export default function ScrollReveal({
  children,
  className,
  index = 0,
  threshold = 0.12,
  as: Tag = "div",
}: Props) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // No observer support: show immediately rather than leaving it hidden.
    if (typeof IntersectionObserver === "undefined") {
      el.classList.add("is-visible");
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            // Reveal is one-way — stop watching so scrolling back up doesn't
            // replay it.
            observer.unobserve(entry.target);
          }
        }
      },
      { threshold, rootMargin: "0px 0px -40px 0px" },
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold]);

  return (
    <Tag
      ref={ref as never}
      className={cn("reveal-on-scroll", className)}
      style={{ "--i": index } as React.CSSProperties}
    >
      {children}
    </Tag>
  );
}
