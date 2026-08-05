/**
 * Chart palette — MITHAQ.
 *
 * The categorical order below is VALIDATED, not chosen by eye. Running
 * dataviz/scripts/validate_palette.js against a light surface returns:
 *
 *   Lightness band      PASS  all 5 inside L 0.43–0.77
 *   Chroma floor        PASS  all 5 >= 0.1
 *   CVD separation      PASS  worst adjacent ΔE 26.1 (deutan)
 *   Normal-vision floor PASS  worst adjacent ΔE 29.3
 *   Contrast vs surface PASS  all 5 >= 3:1
 *
 * Hues are assigned in this fixed order and never cycled. A sixth category
 * folds into "أخرى" rather than inventing a hue — a generated hue is
 * indistinguishable from an existing one under colour-vision deficiency.
 */
export const CATEGORICAL = ["#059669", "#1D4ED8", "#B45309", "#7C3AED", "#BE123C"] as const;

/** Single hue, light → dark. For magnitude, where more is darker. */
export const SEQUENTIAL = ["#D1FAE5", "#6EE7B7", "#34D399", "#059669", "#047857", "#04553D"] as const;

/**
 * Status colours are reserved: they mean state, never "series 4", and always
 * ship with an icon or label rather than colour alone.
 */
export const STATUS = {
  good: "#059669",
  warning: "#B45309",
  serious: "#C2410C",
  critical: "#BE123C",
  neutral: "#64748B",
} as const;

/** Recessive furniture. Grid and axes must never compete with the marks. */
export const INK = {
  grid: "#E2E8F0",
  axis: "#CBD5E1",
  label: "#64748B",
  strong: "#0F172A",
  surface: "#FFFFFF",
} as const;

export type CategoricalIndex = 0 | 1 | 2 | 3 | 4;
