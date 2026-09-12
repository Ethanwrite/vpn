/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // 星火 VPN：奶油白纸面 / 黑色墨色 / 黑金 / 极少量暗红做状态强调
        paper: {
          DEFAULT: "#F6F4EF",
          raised: "#FCFBF8",
          sunken: "#EAE6DF",
        },
        ink: {
          900: "#282825",
          700: "#1E1C19",
          500: "#6B6459",
          300: "#9A9184",
          100: "#DCD4C4",
        },
        gold: {
          DEFAULT: "#922D28",
          light: "#B86C61",
          deep: "#87342F",
        },
        signal: "#8E1B13",
      },
      backgroundImage: {
        "gold-gradient": "linear-gradient(135deg, #B86C61 0%, #922D28 100%)",
        "ink-gradient": "linear-gradient(135deg, #1E1C19 0%, #282825 100%)",
        // 纸面底纹：顶部一层极淡的暖金光晕 + 构成主义网格（合成一条，避免多个
        // background-image 工具类互相覆盖）
        "paper-field": "none",
      },
      backgroundSize: {
        "paper-field": "100% 100%, 72px 72px, 72px 72px",
      },
      // 发丝边与半透明叠色用到的非默认档位；@apply 只认 theme 里声明过的值
      opacity: {
        8: "0.08",
        12: "0.12",
        15: "0.15",
        35: "0.35",
        45: "0.45",
      },
      boxShadow: {
        // 构成主义：不用柔光，用硬边位移投影
        block: "none",
        "block-gold": "none",
        hair: "0 1px 0 rgba(13,13,12,0.10)",
      },
      borderRadius: {
        brand: "14px",
      },
      keyframes: {
        "pulse-ring": {
          "0%": { transform: "scale(0.62)", opacity: "0.85" },
          "100%": { transform: "scale(1.55)", opacity: "0" },
        },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "spin-slow": {
          to: { transform: "rotate(360deg)" },
        },
        "ring-close": {
          from: { strokeDashoffset: "566" },
          to: { strokeDashoffset: "0" },
        },
      },
      animation: {
        "pulse-ring": "pulse-ring 1.15s cubic-bezier(0.2,0.7,0.3,1) 1 both",
        "fade-in": "fade-in 0.3s ease-out",
        "spin-slow": "spin-slow 1.2s linear infinite",
        "ring-close": "ring-close 1.25s cubic-bezier(0.5,0,0.2,1) forwards",
      },
    },
  },
  plugins: [],
};
