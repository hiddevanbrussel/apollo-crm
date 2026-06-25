/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Neutral "interactive" scale: dark primary buttons, dark links,
        // subtle tinted backgrounds. Keeps the UI monochrome and calm.
        brand: {
          50: "#f4f5f7",
          100: "#e8eaee",
          200: "#d6d9e0",
          300: "#b3b8c4",
          400: "#878d9c",
          500: "#565d6d",
          600: "#2b303b",
          700: "#21252e",
          800: "#191c23",
          900: "#111419",
        },
        // Structural greys for text, borders and surfaces.
        ink: {
          50: "#f7f8fa",
          100: "#eef0f3",
          200: "#eceef2",
          300: "#d8dce3",
          400: "#98a0ae",
          500: "#69717f",
          600: "#4d5562",
          700: "#3b424e",
          800: "#2a2f39",
          900: "#1b1f27",
        },
        // Warm accent reserved for the brand mark / logo.
        accent: {
          50: "#fff5ed",
          100: "#ffe7d3",
          200: "#ffcaa5",
          400: "#ff8a4c",
          500: "#fb6514",
          600: "#ea580c",
        },
        // The canvas the app "card" floats on.
        canvas: "#e7e8eb",
      },
      boxShadow: {
        card: "0 1px 2px 0 rgba(16,24,40,0.02)",
        soft: "0 4px 20px -6px rgba(16,24,40,0.06)",
        shell: "0 8px 28px -8px rgba(16,24,40,0.08)",
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
