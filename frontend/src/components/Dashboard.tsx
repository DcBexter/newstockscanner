import { Box, Container, Paper, Typography, Button, IconButton, Tooltip, useTheme, PaletteMode, Stack } from '@mui/material';
import { LightMode, DarkMode, VisibilityOff, Visibility } from '@mui/icons-material';
import ListingsTable from './ListingsTable';
import StatisticsChart from './StatisticsChart';
import ExchangeFilter from './ExchangeFilter';
import MonthPagination from './MonthPagination';
import ScanButton from './ScanButton';
import NotificationSection from './NotificationSection';
import { useAppContext } from '../context/useAppContext';
import { findCommonExchanges, isExchangeSelected } from '../utils/exchangeUtils';
import { EXCHANGE_CODES } from '../constants/exchanges';

interface DashboardProps {
  toggleColorMode: () => void;
  currentTheme: PaletteMode;
}

export default function Dashboard({ toggleColorMode, currentTheme }: DashboardProps) {
  const { state, dispatch, actions } = useAppContext();
  const theme = useTheme();

  // Destructure state for easier access
  const {
    selectedExchange,
    days,
    startDate,
    endDate,
    isPaginationMode,
    listings,
    exchanges,
    statistics,
    isLoadingListings,
    error,
    showStatistics
  } = state;

  // Handle month change from the MonthPagination component
  const handleMonthChange = (start: string, end: string) => {
    dispatch(actions.setDateRange(start, end));
  };

  // Switch back to days-based filtering
  const handleSwitchToDaysMode = (daysValue: number) => {
    dispatch(actions.setDays(daysValue));
  };

  // Find common exchanges using utility function
  const { hkexExchange, nasdaqExchange, nyseExchange } = findCommonExchanges(exchanges);

  // Check if common exchanges are selected using utility function
  const isHkexSelected = isExchangeSelected(selectedExchange, hkexExchange);
  const isNasdaqSelected = isExchangeSelected(selectedExchange, nasdaqExchange);
  const isNyseSelected = isExchangeSelected(selectedExchange, nyseExchange);

  // No scan handler needed - moved to ScanButton component

  const paperStyle = {
    p: 3, 
    height: '100%',
    boxShadow: 3,
  };

  return (
    <Container maxWidth={false} sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        mb: 3, 
        alignItems: 'center',
        pb: 2
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <img 
            src="/logo.png" 
            alt="New Listings Monitor Logo" 
            style={{ 
              height: '50px', 
              width: 'auto',
              padding: '3px',
              background: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.03)', 
              borderRadius: '4px'
            }} 
          />
          <Typography variant="h4" component="h1" fontWeight="bold">
            Financial Listings Monitor
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <NotificationSection />

          <Tooltip title={`Switch to ${currentTheme === 'dark' ? 'light' : 'dark'} mode`}>
            <IconButton onClick={toggleColorMode} color="primary">
              {currentTheme === 'dark' ? <LightMode /> : <DarkMode />}
            </IconButton>
          </Tooltip>

          <ScanButton exchangeCode={EXCHANGE_CODES.HKEX} isSelected={isHkexSelected} />
          <ScanButton exchangeCode={EXCHANGE_CODES.NASDAQ} isSelected={isNasdaqSelected} />
          <ScanButton exchangeCode={EXCHANGE_CODES.NYSE} isSelected={isNyseSelected} />
        </Box>
      </Box>

      {/* Notification handling moved to NotificationSection component */}

      {error && (
        <Paper sx={{ p: 2, mb: 3, bgcolor: 'error.light', color: 'error.contrastText' }}>
          <Typography fontWeight="medium">{error}</Typography>
        </Paper>
      )}

      <Stack spacing={3}>
        {/* Filters */}
        <Box>
          <Paper sx={{ p: 2, boxShadow: 2 }}>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, alignItems: 'flex-start', justifyContent: 'flex-start' }}>
              <ExchangeFilter
                exchanges={exchanges}
                value={selectedExchange}
                onChange={(value) => dispatch(actions.setSelectedExchange(value))}
              />

              <MonthPagination 
                onMonthChange={handleMonthChange} 
                onSwitchToDays={handleSwitchToDaysMode}
                isPaginationMode={isPaginationMode}
              />

              <Button
                variant="outlined"
                color="primary"
                onClick={() => dispatch(actions.toggleStatistics())}
                sx={{ height: '56px' }}
                startIcon={showStatistics ? <VisibilityOff /> : <Visibility />}
              >
                {showStatistics ? 'Hide Statistics' : 'Show Statistics'}
              </Button>
            </Box>
          </Paper>
        </Box>

        {/* Statistics Section */}
        {showStatistics && (
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={3}>
            {/* Stats */}
            <Box sx={{ width: { xs: '100%', md: '25%' } }}>
              <Paper sx={paperStyle}>
                <Typography variant="h6" gutterBottom color="primary" fontWeight="bold">
                  Listings Statistics by Exchange
                </Typography>
                <Box>
                  {statistics?.exchange_stats?.map((stat) => (
                    <Box key={stat.code} sx={{ mb: 2 }}>
                      <Typography variant="subtitle1" fontWeight="medium">{stat.name}</Typography>
                      <Typography variant="h4" color="primary" fontWeight="bold">{stat.total_listings}</Typography>
                      <Typography variant="caption" color="text.secondary">Total Listings</Typography>
                    </Box>
                  ))}
                </Box>
              </Paper>
            </Box>

            {/* Chart */}
            <Box sx={{ width: { xs: '100%', md: '75%' } }}>
              <Paper sx={paperStyle}>
                <Typography variant="h6" gutterBottom color="primary" fontWeight="bold">
                  Daily Listing Activity Trend
                </Typography>
                <StatisticsChart data={statistics?.daily_stats || []} />
              </Paper>
            </Box>
          </Stack>
        )}

        {/* Listings Table - Full Width */}
        <Box>
          <Paper sx={{ p: 3, boxShadow: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" color="primary" fontWeight="bold">
                {isPaginationMode 
                  ? `Financial Listings (${startDate} to ${endDate})` 
                  : `Recent Financial Listings (Last ${days} Days)`
                }
              </Typography>

              <Typography variant="subtitle2" color="text.secondary">
                {listings.length} listings found
              </Typography>
            </Box>
            <ListingsTable data={listings} isLoading={isLoadingListings} />
          </Paper>
        </Box>
      </Stack>
    </Container>
  );
} 
