import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        blurple: "#5865F2",
        discord: "#313338",
        "discord-dark": "#2b2d31",
        "discord-darker": "#1e1f22",
        "discord-input": "#1e1f22",
        "wordlock-green": "#57F287",
        "wordlock-yellow": "#FEE75C",
        "wordlock-red": "#ED4245",
        "wordlock-pink": "#EB459E",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui"],
      },
    },
  },
  plugins: [],
};

export default config;
