/**
 * AURORA Tailwind preset — design tokens from docs/architecture/ui-ux-plan.md §7.
 * Dark-first. Apps extend this preset rather than redefining tokens.
 */
module.exports = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Backgrounds / surfaces (dark-first)
        base: "#0B0E14",
        surface: "#141925",
        elevated: "#1C2333",
        border: "#26304A",
        // Text
        "text-primary": "#E6EAF2",
        "text-muted": "#8A93A6",
        // Brand
        brand: { DEFAULT: "#3B82F6", accent: "#22D3EE" },
        // Semantic / status
        positive: "#22C55E",
        warning: "#F59E0B",
        negative: "#EF4444",
        info: "#3B82F6",
        // Risk severity ramp (low -> critical)
        risk: {
          low: "#22C55E",
          moderate: "#EAB308",
          high: "#F97316",
          critical: "#EF4444",
        },
      },
      borderRadius: { sm: "6px", md: "10px", lg: "16px" },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["Roboto Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
