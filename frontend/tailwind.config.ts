import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef7f2",
          100: "#d6ecdf",
          600: "#1a7f4e",
          700: "#136340",
          800: "#0f4d33",
        },
        // Enterprise dashboard palette (F5) — see lib/chartColors.ts for chart usage.
        arctic: "#F1F6F4",
        mint: "#D9E8E2",
        forsythia: "#FFC801",
        saffron: "#FF9932",
        nocturnal: "#114C5A",
        oceanic: "#172B36",
      },
    },
  },
  plugins: [],
};
export default config;
