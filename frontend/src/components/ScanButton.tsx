import { Refresh } from '@mui/icons-material';
import { Button } from '@mui/material';
import { api } from '../api/client';
import { useAppContext } from '../context/useAppContext';

// Helper function for logging errors that only runs in development mode
function devError(error: unknown): void {
  if (import.meta.env.DEV) {
    console.error(error);
  }
}

interface ScanButtonProps {
  exchangeCode: string;
  isSelected: boolean;
}

/**
 * Button component for triggering a scan for a specific exchange
 */
export default function ScanButton({ exchangeCode, isSelected }: ScanButtonProps) {
  const { state, dispatch, actions } = useAppContext();
  const { isScanning, selectedExchange, days, previousListingsCount } = state;

  // Don't render if the exchange is not selected
  if (!isSelected)
    return null;

  /**
   * Handle the scan button click
   */
  const handleExchangeScan = async () => {
    if (isScanning)
      return;
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
    }
    catch (err) {
      dispatch(actions.setError(`Failed to trigger ${exchangeCode} scan`));
      devError(err);
    }
    finally {
      dispatch(actions.setScanning(false));
    }
  };

  // Wrapper function to handle the async function without returning its promise
  const handleClick = () => {
    void handleExchangeScan();
  };

  return (
    <Button
      variant="contained"
      onClick={handleClick}
      disabled={isScanning}
      startIcon={<Refresh />}
      size="large"
    >
      {isScanning ? 'Scanning...' : `SCAN ${exchangeCode}`}
    </Button>
  );
}
