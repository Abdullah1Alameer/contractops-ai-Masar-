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
      },
    },
  },
  plugins: [],
};
export default config;
