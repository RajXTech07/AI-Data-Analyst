/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#4F46E5",
          hover: "#4338CA",
          soft: "#EEF2FF",
        },
        accent: {
          DEFAULT: "#0D9488", // Evidence Teal
          soft: "#F0FDFA",
        },
        canvas: "#F8FAFC", // Paper Slate
        surface: "#FFFFFF",
        hairline: "#E2E8F0", // Hairline Border
        ink: {
          DEFAULT: "#0F172A",
          body: "#334155",
          muted: "#64748B",
        },
        success: {
          DEFAULT: "#15803D",
          soft: "#DCFCE7",
        },
        warning: {
          DEFAULT: "#B45309",
          soft: "#FEF3C7",
        },
        danger: {
          DEFAULT: "#B91C1C",
          soft: "#FEE2E2",
        },
        info: {
          DEFAULT: "#1D4ED8",
          soft: "#DBEAFE",
        },
        // Dark theme semantic mappings
        dark: {
          primary: "#818CF8",
          canvas: "#0B1120",
          surface: "#111827",
          border: "#1F2937",
          "text-strong": "#F8FAFC",
          text: "#CBD5E1",
          "text-muted": "#94A3B8",
        }
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
      },
      borderRadius: {
        card: "14px",
        btn: "10px",
        dropzone: "16px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(15,23,42,0.06)",
        modal: "0 10px 25px -5px rgba(15, 23, 42, 0.12), 0 8px 10px -6px rgba(15, 23, 42, 0.08)",
      }
    },
  },
  plugins: [],
}

