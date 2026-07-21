/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#f5f7fa",
        panel: "#ffffff",
        ink: "#17202a",
        muted: "#5d6b7c",
        line: "#d8dee8",
        brand: "#0f766e",
        accent: "#2563eb",
        danger: "#b42318"
      },
      boxShadow: {
        overlay: "0 24px 80px rgba(15, 23, 42, 0.28)"
      }
    }
  },
  plugins: []
};
