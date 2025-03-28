import { createTheme } from "@mui/material/styles";

// Define spacing constants
const SPACING = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
};

// Define size constants
const SIZES = {
  minWidth: {
    formControl: 200,
    button: 120,
    dialog: 400,
  },
  maxWidth: {
    container: 1200,
    card: 800,
  },
  height: {
    appBar: 64,
    footer: 48,
  },
};

// Define color constants
const COLORS = {
  primary: {
    main: "#1976d2",
    light: "#42a5f5",
    dark: "#1565c0",
  },
  secondary: {
    main: "#9c27b0",
    light: "#ba68c8",
    dark: "#7b1fa2",
  },
  error: {
    main: "#d32f2f",
    light: "#ef5350",
    dark: "#c62828",
  },
  warning: {
    main: "#ed6c02",
    light: "#ff9800",
    dark: "#e65100",
  },
  info: {
    main: "#0288d1",
    light: "#03a9f4",
    dark: "#01579b",
  },
  success: {
    main: "#2e7d32",
    light: "#4caf50",
    dark: "#1b5e20",
  },
  grey: {
    50: "#fafafa",
    100: "#f5f5f5",
    200: "#eeeeee",
    300: "#e0e0e0",
    400: "#bdbdbd",
    500: "#9e9e9e",
    600: "#757575",
    700: "#616161",
    800: "#424242",
    900: "#212121",
  },
};

// Create and export the theme
const theme = createTheme({
  palette: {
    primary: {
      main: COLORS.primary.main,
      light: COLORS.primary.light,
      dark: COLORS.primary.dark,
    },
    secondary: {
      main: COLORS.secondary.main,
      light: COLORS.secondary.light,
      dark: COLORS.secondary.dark,
    },
    error: {
      main: COLORS.error.main,
      light: COLORS.error.light,
      dark: COLORS.error.dark,
    },
    warning: {
      main: COLORS.warning.main,
      light: COLORS.warning.light,
      dark: COLORS.warning.dark,
    },
    info: {
      main: COLORS.info.main,
      light: COLORS.info.light,
      dark: COLORS.info.dark,
    },
    success: {
      main: COLORS.success.main,
      light: COLORS.success.light,
      dark: COLORS.success.dark,
    },
  },
  spacing: SPACING.md, // Base spacing unit
});

// Export constants for direct use in components
export { COLORS, SIZES, SPACING };

// Export the theme as default
export default theme;
