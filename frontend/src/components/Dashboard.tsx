import { Box, Container, Paper, Typography, Button, IconButton, Tooltip, useTheme, PaletteMode, Snackbar, Alert, Badge, Stack } from '@mui/material';
import { LightMode, DarkMode, Refresh, Notifications, VisibilityOff, Visibility } from '@mui/icons-material';
import ListingsTable from './ListingsTable';
import StatisticsChart from './StatisticsChart';
import ExchangeFilter from './ExchangeFilter';
import MonthPagination from './MonthPagination';
import { useAppContext } from '../context/AppContext';
import { api } from '../api/client';

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
    isScanning,
    error,
    showStatistics,
    hasNewListings,
    notificationOpen,
    newListingsCount,
    previousListingsCount
  } = state;

  // Handle notification close
  const handleNotificationClose = () => {
    dispatch(actions.setNotificationOpen(false));
  };

  // Acknowledge new listings
  const acknowledgeNewListings = () => {
    dispatch(actions.acknowledgeNewListings());
  };

  // Request notification permission
  const requestNotificationPermission = () => {
    if (Notification.permission !== 'granted' && Notification.permission !== 'denied') {
      Notification.requestPermission().then(permission => {
        console.log(`Notification permission ${permission}`);
      });
    }
  };

  // Handle month change from the MonthPagination component
  const handleMonthChange = (start: string, end: string) => {
    dispatch(actions.setDateRange(start, end));
  };

  // Switch back to days-based filtering
  const handleSwitchToDaysMode = (daysValue: number) => {
    dispatch(actions.setDays(daysValue));
  };

  // Exchange codes
  const EXCHANGE_CODES = {
    HKEX: 'HKEX',
    NASDAQ: 'NASDAQ',
    NYSE: 'NYSE'
  };

  // Find exchanges by code or name
  const findExchange = (code: string, nameSubstring: string) => {
    return exchanges.find(exchange => 
      exchange.code === code || 
      exchange.name.toLowerCase().includes(nameSubstring.toLowerCase())
    );
  };

  // Find common exchanges
  const hkexExchange = findExchange(EXCHANGE_CODES.HKEX, 'hong kong');
  const nasdaqExchange = findExchange(EXCHANGE_CODES.NASDAQ, 'nasdaq');
  const nyseExchange = findExchange(EXCHANGE_CODES.NYSE, 'new york');

  // Check if a specific exchange is selected
  const isExchangeSelected = (exchange: typeof hkexExchange) => {
    if (!selectedExchange || !exchange) return false;
    return selectedExchange === exchange.code || selectedExchange === exchange.id.toString();
  };

  // Check if common exchanges are selected
  const isHkexSelected = isExchangeSelected(hkexExchange);
  const isNasdaqSelected = isExchangeSelected(nasdaqExchange);
  const isNyseSelected = isExchangeSelected(nyseExchange);

  // Generic scan handler for any exchange
  const handleExchangeScan = async (exchangeCode: string) => {
    if (isScanning) return;
    dispatch(actions.setScanning(true));
    dispatch(actions.clearError());

    try {
      // Call the scan API with the exchange parameter
      await api.triggerScrape(exchangeCode);

      // Create params for refreshing data after scan
      const params: Record<string, string | number> = { days };
      if (selectedExchange) {
        params.exchange_code = selectedExchange;
      }
      const listingsData = await api.getListings(params);

      // Check if new listings were found during the scan
      if (listingsData.length > previousListingsCount) {
        const newCount = listingsData.length - previousListingsCount;
        dispatch(actions.setNewListings(true, newCount));
      }

      // Update listings data
      dispatch(actions.setListings(listingsData));

      // Refresh statistics
      const statsData = await api.getStatistics(days);
      dispatch(actions.setStatistics(statsData));
    } catch (err) {
      dispatch(actions.setError(`Failed to trigger ${exchangeCode} scan`));
      console.error(err);
    } finally {
      dispatch(actions.setScanning(false));
    }
  };

  // Specific exchange scan handlers
  const handleScan = () => handleExchangeScan(EXCHANGE_CODES.HKEX);
  const handleNasdaqScan = () => handleExchangeScan(EXCHANGE_CODES.NASDAQ);
  const handleNyseScan = () => handleExchangeScan(EXCHANGE_CODES.NYSE);

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
          {hasNewListings && (
            <Tooltip title={`${newListingsCount} new listing${newListingsCount > 1 ? 's' : ''} detected`}>
              <Badge badgeContent={newListingsCount} color="error" overlap="circular">
                <IconButton color="primary" onClick={acknowledgeNewListings}>
                  <Notifications />
                </IconButton>
              </Badge>
            </Tooltip>
          )}
          {Notification.permission !== 'granted' && Notification.permission !== 'denied' && (
            <Tooltip title="Enable notifications">
              <IconButton color="primary" onClick={requestNotificationPermission}>
                <Notifications />
              </IconButton>
            </Tooltip>
          )}
          <Tooltip title={`Switch to ${currentTheme === 'dark' ? 'light' : 'dark'} mode`}>
            <IconButton onClick={toggleColorMode} color="primary">
              {currentTheme === 'dark' ? <LightMode /> : <DarkMode />}
            </IconButton>
          </Tooltip>

          {isHkexSelected && (
            <Button
              variant="contained"
              onClick={handleScan}
              disabled={isScanning}
              startIcon={<Refresh />}
              size="large"
            >
              {isScanning ? 'Scanning...' : 'SCAN HKEX'}
            </Button>
          )}

          {isNasdaqSelected && (
            <Button
              variant="contained"
              onClick={handleNasdaqScan}
              disabled={isScanning}
              startIcon={<Refresh />}
              size="large"
            >
              {isScanning ? 'Scanning...' : 'SCAN NASDAQ'}
            </Button>
          )}

          {isNyseSelected && (
            <Button
              variant="contained"
              onClick={handleNyseScan}
              disabled={isScanning}
              startIcon={<Refresh />}
              size="large"
            >
              {isScanning ? 'Scanning...' : 'SCAN NYSE'}
            </Button>
          )}
        </Box>
      </Box>

      {/* New Listings Notification */}
      <Snackbar 
        open={notificationOpen} 
        autoHideDuration={6000} 
        onClose={handleNotificationClose}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Alert 
          onClose={handleNotificationClose} 
          severity="success" 
          variant="filled"
          sx={{ width: '100%' }}
        >
          {newListingsCount} new listing{newListingsCount > 1 ? 's' : ''} detected!
        </Alert>
      </Snackbar>

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
