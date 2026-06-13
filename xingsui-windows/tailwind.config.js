/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // 品牌蓝紫渐变主题色
        brand: {
          from: "#4F46E5",
          to: "#7C3AED",
          glow: "#6366F1",
        },
        ink: {
          900: "#0B0B14",
          800: "#11111d",
          700: "#181826",
          600: "#22223a",
        },
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%)",
        "brand-radial":
          "radial-gradient(1200px 600px at 50% -10%, rgba(124,58,237,0.25), transparent 60%)",
      },
      boxShadow: {
        glass: "0 8px 32px 0 rgba(31, 38, 135, 0.25)",
        glow: "0 0 40px 0 rgba(99, 102, 241, 0.45)",
      },
      backdropBlur: {
        glass: "14px",
      },
      keyframes: {
        "pulse-ring": {
          "0%": { transform: "scale(0.95)", opacity: "0.7" },
          "70%": { transform: "scale(1.25)", opacity: "0" },
          "100%": { opacity: "0" },
        },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "spin-slow": {
          to: { transform: "rotate(360deg)" },
        },
      },
      animation: {
        "pulse-ring": "pulse-ring 2s cubic-bezier(0.215,0.61,0.355,1) infinite",
        "fade-in": "fade-in 0.3s ease-out",
        "spin-slow": "spin-slow 1.2s linear infinite",
      },
    },
  },
  plugins: [],
};
