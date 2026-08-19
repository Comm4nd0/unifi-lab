/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Palette lifted from the UniFi Network console's dark theme.
        ink: {
          950: "#0b0d10",
          900: "#111318",
          850: "#161920",
          800: "#1c2029",
          700: "#252a35",
          600: "#333a48",
          500: "#4a5263",
          400: "#6b7488",
          300: "#9aa3b5",
          200: "#c7cedb",
        },
        unifi: {
          DEFAULT: "#0559c9",
          bright: "#1f7aff",
          soft: "#123a72",
        },
        ok: "#2fb87a",
        warn: "#f2a900",
        bad: "#f0343f",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.6)",
      },
    },
  },
  plugins: [],
};
