import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: "#111218",
        graphite: "#1f2230",
        panel: "#ffffff",
        line: "#d8d7e6",
        mist: "#6d7283",
        bone: "#fbfaff",
        lilac: "#7d64ff",
        iris: "#5a43dd",
        frost: "#17181f",
        success: "#338065",
        caution: "#9a7312",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["DM Serif Display", "Georgia", "serif"],
      },
      boxShadow: {
        panel: "0 20px 60px rgba(36, 29, 84, 0.08)",
        card: "0 4px 24px rgba(40, 27, 105, 0.07), 0 1px 4px rgba(40, 27, 105, 0.04)",
        "card-hover": "0 12px 40px rgba(40, 27, 105, 0.13), 0 2px 8px rgba(40, 27, 105, 0.06)",
      },
      keyframes: {
        floatIn: {
          "0%": { opacity: "0", transform: "translateY(20px) scale(0.98)" },
          "100%": { opacity: "1", transform: "translateY(0) scale(1)" },
        },
        pulseGrid: {
          "0%, 100%": { opacity: "0.14" },
          "50%": { opacity: "0.28" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-400px 0" },
          "100%": { backgroundPosition: "400px 0" },
        },
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        spinSlow: {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
      },
      animation: {
        "float-in": "floatIn 700ms cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "pulse-grid": "pulseGrid 8s ease-in-out infinite",
        shimmer: "shimmer 2s linear infinite",
        "fade-up": "fadeUp 500ms cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "spin-slow": "spinSlow 3s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
