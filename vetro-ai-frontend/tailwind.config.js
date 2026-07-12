/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      // Named tokens for the existing "dark/amber incident log" look,
      // which today is only expressed via repeated inline arbitrary-hex
      // classes across ChatApp/ChatInterface/Sidebar/MarkdownMessage
      // (e.g. bg-[#0B1120], text-[#D4A24C]). Purely additive -- those
      // existing components are left untouched, this just gives the new
      // Network/Map/Trends/Offenders views the same palette as tokens
      // (bg-surface-panel, text-accent, etc.) instead of a 6th/7th/8th
      // repetition of the same hex literals.
      colors: {
        surface: {
          base: "#0B1120",
          raised: "#0E1526",
          panel: "#151B2E",
          inset: "#161D2E",
        },
        line: {
          DEFAULT: "#2A3348",
        },
        accent: {
          DEFAULT: "#D4A24C",
          hover: "#E0B15F",
        },
        ink: {
          primary: "#E4E7EC",
          secondary: "#C8CCD8",
          muted: "#A8AEC0",
          faint: "#6B7488",
          dim: "#4A5268",
        },
        status: {
          success: "#3A6B4C",
          error: "#B0503C",
        },
      },
    },
  },
  plugins: [],
}

