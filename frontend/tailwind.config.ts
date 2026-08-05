import type { Config } from "tailwindcss";

/**
 * Riyadh Emerald — ContractOps AI / ميثاق
 *
 * Semantic intent, so a contract's state is legible at a glance:
 *   emerald  → safe, compliant, on track
 *   gold     → a clock is running (time-bar, notice window)
 *   amber    → that clock is nearly out
 *   rose     → breached, forfeited, failed
 *   violet   → the AI produced this, a human has not confirmed it
 *
 * Existing token names (brand/neutral/success/danger/warning/info/muted) are
 * retained and re-tuned rather than replaced, so the ~30 components already
 * using them pick up the new palette without edits.
 */
const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      borderRadius: {
        card: "14px",
        xl2: "18px",
        xl3: "24px",
        xl4: "32px",
      },

      fontFamily: {
        ui: ["var(--font-ui)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "Georgia", "serif"],
        wordmark: ["var(--font-wordmark)", "Georgia", "serif"],
      },
      colors: {
        // Primary. 600 is the brand itself so `bg-brand-600 hover:bg-brand-700`
        // — the idiom already used across the app — lands on brand.
        brand: {
          50: "#ECFDF5",
          100: "#D1FAE5",
          200: "#A7F3D0",
          300: "#6EE7B7",
          400: "#34D399",
          500: "#059669",
          600: "#047857", // Riyadh Emerald — primary
          700: "#036045",
          800: "#064E3B",
          900: "#04352A",
          950: "#022018",
        },

        // Cool navy-slate. Carries depth and dark-mode surfaces; deliberately
        // blue-leaning so it reads as a counterweight to the green rather than
        // as a muddy neutral green.
        ink: {
          50: "#F6F8FB",
          100: "#EDF1F7",
          200: "#DCE3ED",
          300: "#C0CBDB",
          400: "#8B9AB0",
          500: "#5F6E85",
          600: "#43526A",
          700: "#1E293B",
          800: "#141E2E",
          900: "#0B1220",
          950: "#060A12",
        },

        // Neutrals re-pointed onto the same cool axis as ink so greys and
        // surfaces never disagree about temperature.
        neutral: {
          50: "#F8FAFC",
          100: "#F1F5F9",
          200: "#E2E8F0",
          300: "#CBD5E1",
          400: "#94A3B8",
          500: "#64748B",
          600: "#475569",
          700: "#334155",
          800: "#1E293B",
          900: "#0F172A",
        },

        // Cyber jade — the high-energy accent. Reserved for live/AI states and
        // glow edges; too luminous to carry body text.
        jade: {
          400: "#00F5A0",
          500: "#00D48A",
          600: "#00B375",
        },

        // Porcelain / obsidian page bases.
        porcelain: "#F9FAFB",
        obsidian: "#080C14",

        // Deep pine range, from the brand reference. Used for the one dark
        // anchor panel on an otherwise white page — never as a page background.
        pine: {
          950: "#051F20",
          900: "#0B2B26",
          800: "#163832",
          700: "#235347",
          300: "#8EB69B",
          100: "#DAF1DE",
        },

        // A clock is running. Reserved for time-bar / notice windows — the
        // product's flagship risk, so it gets its own hue nothing else uses.
        gold: {
          50: "#FBF6E9",
          100: "#F6EBCB",
          200: "#EDD79B",
          400: "#E0B75C",
          500: "#D9A441",
          600: "#B4832C",
          700: "#8A6320",
        },

        // AI-generated, not yet human-confirmed.
        ai: {
          50: "#F5F3FF",
          100: "#EDE9FE",
          200: "#DDD6FE",
          400: "#A78BFA",
          500: "#7C5CFF",
          600: "#6D3EF5",
          700: "#5B2FD1",
        },

        success: {
          50: "#ECFDF5",
          100: "#D1FAE5",
          200: "#A7F3D0",
          500: "#10B981",
          600: "#059669",
          700: "#047857",
        },
        danger: {
          50: "#FFF1F3",
          100: "#FFE4E8",
          200: "#FECDD5",
          500: "#F43F5E",
          600: "#E11D48",
          700: "#BE123C",
        },
        warning: {
          50: "#FFFBEB",
          100: "#FEF3C7",
          200: "#FDE68A",
          500: "#F59E0B",
          600: "#D97706",
          700: "#B45309",
        },
        info: {
          50: "#EFF6FF",
          100: "#DBEAFE",
          200: "#BFDBFE",
          500: "#3B82F6",
          600: "#2563EB",
          700: "#1D4ED8",
        },
        muted: {
          50: "#F8FAFC",
          100: "#F1F5F9",
          200: "#E2E8F0",
        },
      },

      boxShadow: {
        // Tinted with the ink hue rather than pure black — shadows on a warm
        // white read as dirt when they are neutral grey.
        card: "0 1px 2px rgb(11 18 32 / 0.04), 0 1px 3px rgb(11 18 32 / 0.06)",
        cardHover: "0 8px 24px -6px rgb(11 18 32 / 0.10), 0 2px 6px rgb(11 18 32 / 0.05)",
        panel: "0 4px 24px -2px rgb(11 18 32 / 0.07), 0 0 0 1px rgb(11 18 32 / 0.04)",
        "elevation-1": "0 1px 2px rgb(11 18 32 / 0.05)",
        "elevation-2": "0 4px 12px rgb(11 18 32 / 0.07)",
        "elevation-3": "0 12px 32px rgb(11 18 32 / 0.10)",
        "elevation-4": "0 24px 60px -12px rgb(11 18 32 / 0.18)",
        // Focus / emphasis glows.
        glow: "0 0 0 1px rgb(4 120 87 / 0.16), 0 8px 28px -8px rgb(4 120 87 / 0.32)",
        "glow-gold": "0 0 0 1px rgb(217 164 65 / 0.22), 0 8px 28px -8px rgb(217 164 65 / 0.38)",
        "glow-danger": "0 0 0 1px rgb(225 29 72 / 0.20), 0 8px 28px -8px rgb(225 29 72 / 0.36)",
        "inset-hairline": "inset 0 0 0 1px rgb(11 18 32 / 0.06)",
      },

      backgroundImage: {
        "brand-sheen": "linear-gradient(135deg, #047857 0%, #059669 45%, #0E7490 100%)",
        "gold-sheen": "linear-gradient(135deg, #B4832C 0%, #D9A441 50%, #EDD79B 100%)",
        "ai-sheen": "linear-gradient(135deg, #5B2FD1 0%, #7C5CFF 50%, #A78BFA 100%)",
        "mesh-emerald":
          "radial-gradient(at 12% 18%, rgb(4 120 87 / 0.14) 0px, transparent 55%), radial-gradient(at 88% 8%, rgb(14 116 144 / 0.10) 0px, transparent 50%), radial-gradient(at 68% 92%, rgb(217 164 65 / 0.08) 0px, transparent 50%)",
        shimmer:
          "linear-gradient(90deg, transparent 0%, rgb(255 255 255 / 0.55) 50%, transparent 100%)",
      },

      keyframes: {
        fadeIn: { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        // Section / card entrance. Slightly longer travel than slideUp so
        // staggered groups read as a wave rather than a twitch.
        riseIn: {
          "0%": { opacity: "0", transform: "translateY(18px) scale(0.985)" },
          "100%": { opacity: "1", transform: "translateY(0) scale(1)" },
        },
        // Direction-agnostic: uses no X translation, so it is identical in
        // RTL and LTR and needs no mirroring.
        scaleIn: {
          "0%": { opacity: "0", transform: "scale(0.96)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
        // Countdown / live indicators.
        pulseRing: {
          "0%": { transform: "scale(0.92)", opacity: "0.7" },
          "70%": { transform: "scale(1.6)", opacity: "0" },
          "100%": { transform: "scale(1.6)", opacity: "0" },
        },
        breathe: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
        // Slow drift on the mesh gradient — perceptible only over ~18s, which
        // keeps a data-dense screen from feeling busy.
        meshDrift: {
          "0%, 100%": { backgroundPosition: "0% 0%, 100% 0%, 60% 100%" },
          "50%": { backgroundPosition: "10% 12%, 88% 8%, 52% 88%" },
        },
        drawRing: {
          "0%": { strokeDashoffset: "var(--ring-circumference, 264)" },
          "100%": { strokeDashoffset: "var(--ring-offset-target, 0)" },
        },
        // AI audit pass — a light bar travelling down a document preview.
        // Vertical only, so it is direction-agnostic under RTL.
        laser: {
          "0%": { transform: "translateY(-120%)", opacity: "0" },
          "12%": { opacity: "1" },
          "88%": { opacity: "1" },
          "100%": { transform: "translateY(820%)", opacity: "0" },
        },
        // Live-status dot.
        livePulse: {
          "0%": { transform: "scale(0.85)", opacity: "0.9" },
          "70%": { transform: "scale(2.2)", opacity: "0" },
          "100%": { transform: "scale(2.2)", opacity: "0" },
        },
      },

      animation: {
        fadeIn: "fadeIn 0.25s ease-out both",
        slideUp: "slideUp 0.3s ease-out both",
        riseIn: "riseIn 0.55s cubic-bezier(0.22, 1, 0.36, 1) both",
        scaleIn: "scaleIn 0.35s cubic-bezier(0.22, 1, 0.36, 1) both",
        shimmer: "shimmer 1.6s infinite linear",
        pulseRing: "pulseRing 2.2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        breathe: "breathe 2.4s ease-in-out infinite",
        float: "float 6s ease-in-out infinite",
        meshDrift: "meshDrift 18s ease-in-out infinite",
        drawRing: "drawRing 1.1s cubic-bezier(0.22, 1, 0.36, 1) both",
        laser: "laser 3.6s cubic-bezier(0.45, 0, 0.55, 1) infinite",
        livePulse: "livePulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },

      transitionTimingFunction: {
        // Decelerating ease — motion that arrives and settles rather than
        // stopping dead. Used for every entrance and layout transition.
        settle: "cubic-bezier(0.22, 1, 0.36, 1)",
        emphasis: "cubic-bezier(0.34, 1.56, 0.64, 1)",
      },
    },
  },
  plugins: [],
};
export default config;
