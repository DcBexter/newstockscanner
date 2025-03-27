import type { PaletteMode } from '@mui/material';
import { createTheme, CssBaseline, ThemeProvider } from '@mui/material';
import { useMemo, useState } from 'react';
import Dashboard from './components/Dashboard';
import { AppProvider } from './context/AppContext';

function App() {
  const [mode, setMode] = useState<PaletteMode>('dark');

  const theme = useMemo(
    () =>
      createTheme({
        palette: {
          mode,
          primary: {
            main: '#4caf50',
            light: '#81c784',
            dark: '#388e3c',
            contrastText: '#fff',
          },
          secondary: {
            main: '#f44336',
            light: '#e57373',
            dark: '#d32f2f',
            contrastText: '#fff',
          },
          error: {
            main: '#f44336',
          },
          warning: {
            main: '#ff9800',
          },
          info: {
            main: '#29b6f6',
          },
          success: {
            main: '#4caf50',
          },
          ...(mode === 'dark'
            ? {
                background: {
                  default: '#121212',
                  paper: '#1e1e1e',
                },
                text: {
                  primary: '#f5f5f5',
                  secondary: '#b0b0b0',
                },
              }
            : {
                background: {
                  default: '#f5f5f5',
                  paper: '#ffffff',
                },
                text: {
                  primary: '#212121',
                  secondary: '#757575',
                },
              }),
        },
        typography: {
          fontSize: 14,
          fontFamily: [
            '-apple-system',
            'BlinkMacSystemFont',
            '"Segoe UI"',
            'Roboto',
            '"Helvetica Neue"',
            'Arial',
            'sans-serif',
          ].join(','),
          h4: {
            fontWeight: 600,
            fontSize: '1.75rem',
          },
          h6: {
            fontWeight: 600,
            fontSize: '1.25rem',
          },
          body1: {
            fontSize: '1.1rem',
          },
          body2: {
            fontSize: '1rem',
          },
        },
        components: {
          MuiButton: {
            styleOverrides: {
              root: {
                textTransform: 'none',
                fontWeight: 600,
                fontSize: '1rem',
              },
            },
          },
          MuiTableCell: {
            styleOverrides: {
              root: {
                fontSize: '1.1rem',
                padding: '12px 16px',
              },
              head: {
                fontWeight: 600,
              },
            },
          },
          MuiChip: {
            styleOverrides: {
              root: {
                fontSize: '0.9rem',
              },
            },
          },
        },
      }),
    [mode],
  );

  const toggleColorMode = () => {
    setMode(prevMode => (prevMode === 'light' ? 'dark' : 'light'));
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppProvider>
        <Dashboard toggleColorMode={toggleColorMode} currentTheme={mode} />
      </AppProvider>
    </ThemeProvider>
  );
}

export default App;
