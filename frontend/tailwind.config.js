/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#f8fafc",
        primary: "#0e3a45",
        accent: "#14b8a6",
      },
    },
  },
  plugins: [],
};
