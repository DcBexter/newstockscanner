import { useState, useEffect, useMemo, useRef } from 'react';
import { Box, Container, Paper, Typography, Button, IconButton, Tooltip, useTheme, PaletteMode, Snackbar, Alert, Badge, Stack } from '@mui/material';
import { LightMode, DarkMode, Refresh, Notifications, VisibilityOff, Visibility } from '@mui/icons-material';
import { api } from '../api/client';
import ListingsTable from './ListingsTable';
import StatisticsChart from './StatisticsChart';
import ExchangeFilter from './ExchangeFilter';
import MonthPagination from './MonthPagination';
import type { Listing, Exchange, Statistics } from '../api/client';

interface DashboardProps {
  toggleColorMode: () => void;
  currentTheme: PaletteMode;
}

export default function Dashboard({ toggleColorMode, currentTheme }: DashboardProps) {
  // State
  const [selectedExchange, setSelectedExchange] = useState<string>('');
  const [days, setDays] = useState<number>(30);
  const [startDate, setStartDate] = useState<string | null>(null);
  const [endDate, setEndDate] = useState<string | null>(null);
  const [isPaginationMode, setIsPaginationMode] = useState<boolean>(false);
  const [listings, setListings] = useState<Listing[]>([]);
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [statistics, setStatistics] = useState<Statistics | null>(null);
  const [isLoadingListings, setIsLoadingListings] = useState<boolean>(true);
  const [isScanning, setIsScanning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [showStatistics, setShowStatistics] = useState<boolean>(true);
  
  // Notification state
  const [hasNewListings, setHasNewListings] = useState<boolean>(false);
  const [notificationOpen, setNotificationOpen] = useState<boolean>(false);
  const [newListingsCount, setNewListingsCount] = useState<number>(0);
  const previousListingsRef = useRef<number>(0);
  const pollingIntervalRef = useRef<number | null>(null);

  const theme = useTheme();

  // Auto-refresh listings every 5 minutes to check for updates
  useEffect(() => {
    // Setup auto-polling for new listings
    if (pollingIntervalRef.current) {
      window.clearInterval(pollingIntervalRef.current);
    }
    
    pollingIntervalRef.current = window.setInterval(() => {
      // Only poll if the user has granted notification permission
      if (Notification.permission === 'granted') {
        fetchListingsForNotification();
      }
    }, 5 * 60 * 1000); // Check every 5 minutes
    
    // Request notification permission on component mount
    if (Notification.permission !== 'granted' && Notification.permission !== 'denied') {
      Notification.requestPermission();
    }

    return () => {
      if (pollingIntervalRef.current) {
        window.clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, []);

  // Function to fetch listings only for notification purposes
  const fetchListingsForNotification = async () => {
    try {
      const params: Record<string, string | number> = { days };
      if (selectedExchange) {
        params.exchange_code = selectedExchange;
      }
      
      const listingsData = await api.getListings(params);
      const currentCount = listingsData.length;
      
      // If this isn't the first check and we have more listings than before
      if (previousListingsRef.current > 0 && currentCount > previousListingsRef.current) {
        const newCount = currentCount - previousListingsRef.current;
        setNewListingsCount(newCount);
        setHasNewListings(true);
        setNotificationOpen(true);
        
        // Show browser notification if allowed
        if (Notification.permission === 'granted') {
          new Notification('New Financial Listings', {
            body: `${newCount} new listing${newCount > 1 ? 's' : ''} detected!`,
            icon: '/logo.png' // Using the logo for notifications
          });
        }
        
        // Update the listings without setting loading state
        setListings(listingsData);
      }
      
      // Update ref for next comparison
      previousListingsRef.current = currentCount;
      
    } catch (err) {
      console.error('Background polling error:', err);
    }
  };

  // Reset new listings notification when user interacts with the page
  const handleNotificationClose = () => {
    setNotificationOpen(false);
  };

  const acknowledgeNewListings = () => {
    setHasNewListings(false);
    setNotificationOpen(false);
  };

  // Load exchanges
  useEffect(() => {
    const fetchExchanges = async () => {
      try {
        const exchangesData = await api.getExchanges();
        setExchanges(exchangesData);
      } catch (err) {
        setError('Failed to load exchanges');
        console.error(err);
      }
    };

    fetchExchanges();
  }, []);

  // Handle month change from the MonthPagination component
  const handleMonthChange = (start: string, end: string) => {
    setStartDate(start);
    setEndDate(end);
    setIsPaginationMode(true);
    // Clear days filter when using month pagination
    setDays(0);
  };
  
  // Switch back to days-based filtering
  const handleSwitchToDaysMode = (daysValue: number) => {
    setIsPaginationMode(false);
    setStartDate(null);
    setEndDate(null);
    setDays(daysValue);
  };

  // Load listings when filters change
  useEffect(() => {
    const fetchListings = async () => {
      setIsLoadingListings(true);
      try {
        const params: Record<string, string | number> = {};
        
        // Use either date range or days depending on mode
        if (isPaginationMode && startDate && endDate) {
          params.start_date = startDate;
          params.end_date = endDate;
        } else {
          params.days = days;
        }
        
        if (selectedExchange) {
          params.exchange_code = selectedExchange;
        }
        
        const listingsData = await api.getListings(params);
        
        setListings(listingsData);
        
        // Store count for notification comparison
        previousListingsRef.current = listingsData.length;
        
        // Reset notification state when filters change
        setHasNewListings(false);
      } catch (err) {
        setError('Failed to load listings');
        console.error(err);
      } finally {
        setIsLoadingListings(false);
      }
    };

    fetchListings();
  }, [selectedExchange, days, startDate, endDate, isPaginationMode]);

  // Load statistics when days change
  useEffect(() => {
    const fetchStatistics = async () => {
      try {
        // Only fetch statistics with days parameter
        if (!isPaginationMode) {
          const statsData = await api.getStatistics(days);
          setStatistics(statsData);
        }
      } catch (err) {
        setError('Failed to load statistics');
        console.error(err);
      }
    };

    fetchStatistics();
  }, [days, isPaginationMode]);

  // Handle manual scan
  const handleScan = async () => {
    if (isScanning) return;
    setIsScanning(true);
    setError(null);
    
    try {
      // Call the scan API with the HKEX parameter
      await api.triggerScrape('HKEX');
      
      // Create params for refreshing data after scan
      const params: Record<string, string | number> = { days };
      if (selectedExchange) {
        params.exchange_code = selectedExchange;
      }
      const listingsData = await api.getListings(params);
      
      // Check if new listings were found during the scan
      if (listingsData.length > previousListingsRef.current) {
        const newCount = listingsData.length - previousListingsRef.current;
        setNewListingsCount(newCount);
        setHasNewListings(true);
      }
      
      // Update listings data
      setListings(listingsData);
      previousListingsRef.current = listingsData.length;
      
      // Refresh statistics
      const statsData = await api.getStatistics(days);
      setStatistics(statsData);
    } catch (err) {
      setError('Failed to trigger HKEX scan');
      console.error(err);
    } finally {
      setIsScanning(false);
    }
  };

  // Find the HKEX exchange
  const hkexExchange = useMemo(() => {
    return exchanges.find(exchange => 
      exchange.code === 'HKEX' || 
      exchange.name.toLowerCase().includes('hong kong')
    );
  }, [exchanges]);
  
  // Find the NASDAQ exchange
  const nasdaqExchange = useMemo(() => {
    return exchanges.find(exchange => 
      exchange.code === 'NASDAQ' || 
      exchange.name.toLowerCase().includes('nasdaq')
    );
  }, [exchanges]);
  
  // Find the NYSE exchange
  const nyseExchange = useMemo(() => {
    return exchanges.find(exchange => 
      exchange.code === 'NYSE' || 
      exchange.name.toLowerCase().includes('new york')
    );
  }, [exchanges]);
  
  // Check if HKEX is selected
  const isHkexSelected = useMemo(() => {
    if (!selectedExchange || !hkexExchange) return false;
    return selectedExchange === hkexExchange.code || selectedExchange === hkexExchange.id.toString();
  }, [selectedExchange, hkexExchange]);
  
  // Check if NASDAQ is selected
  const isNasdaqSelected = useMemo(() => {
    if (!selectedExchange || !nasdaqExchange) return false;
    return selectedExchange === nasdaqExchange.code || selectedExchange === nasdaqExchange.id.toString();
  }, [selectedExchange, nasdaqExchange]);
  
  // Check if NYSE is selected
  const isNyseSelected = useMemo(() => {
    if (!selectedExchange || !nyseExchange) return false;
    return selectedExchange === nyseExchange.code || selectedExchange === nyseExchange.id.toString();
  }, [selectedExchange, nyseExchange]);

  // Handle NASDAQ scan
  const handleNasdaqScan = async () => {
    if (isScanning) return;
    setIsScanning(true);
    setError(null);
    
    try {
      // Call the scan API with the NASDAQ parameter
      await api.triggerScrape('NASDAQ');
      
      // Create params for refreshing data after scan
      const params: Record<string, string | number> = { days };
      if (selectedExchange) {
        params.exchange_code = selectedExchange;
      }
      const listingsData = await api.getListings(params);
      
      // Check if new listings were found during the scan
      if (listingsData.length > previousListingsRef.current) {
        const newCount = listingsData.length - previousListingsRef.current;
        setNewListingsCount(newCount);
        setHasNewListings(true);
      }
      
      // Update listings data
      setListings(listingsData);
      previousListingsRef.current = listingsData.length;
      
      // Refresh statistics
      const statsData = await api.getStatistics(days);
      setStatistics(statsData);
    } catch (err) {
      setError('Failed to trigger NASDAQ scan');
      console.error(err);
    } finally {
      setIsScanning(false);
    }
  };
  
  // Handle NYSE scan
  const handleNyseScan = async () => {
    if (isScanning) return;
    setIsScanning(true);
    setError(null);
    
    try {
      // Call the scan API with the NYSE parameter
      await api.triggerScrape('NYSE');
      
      // Create params for refreshing data after scan
      const params: Record<string, string | number> = { days };
      if (selectedExchange) {
        params.exchange_code = selectedExchange;
      }
      const listingsData = await api.getListings(params);
      
      // Check if new listings were found during the scan
      if (listingsData.length > previousListingsRef.current) {
        const newCount = listingsData.length - previousListingsRef.current;
        setNewListingsCount(newCount);
        setHasNewListings(true);
      }
      
      // Update listings data
      setListings(listingsData);
      previousListingsRef.current = listingsData.length;
      
      // Refresh statistics
      const statsData = await api.getStatistics(days);
      setStatistics(statsData);
    } catch (err) {
      setError('Failed to trigger NYSE scan');
      console.error(err);
    } finally {
      setIsScanning(false);
    }
  };

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
                onChange={setSelectedExchange}
              />
              
              <MonthPagination 
                onMonthChange={handleMonthChange} 
                onSwitchToDays={handleSwitchToDaysMode}
                isPaginationMode={isPaginationMode}
              />
              
              <Button
                variant="outlined"
                color="primary"
                onClick={() => setShowStatistics(!showStatistics)}
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