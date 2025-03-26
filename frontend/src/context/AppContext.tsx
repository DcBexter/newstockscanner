import React, { createContext, useContext, useReducer, useEffect, useRef } from 'react';
import { AppState, AppAction } from './types';
import { reducer, initialState } from './reducer';
import * as actions from './actions';
import { api } from '../api/client';

// Create context
interface AppContextType {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
  actions: typeof actions;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

// Provider component
interface AppProviderProps {
  children: React.ReactNode;
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(reducer, initialState);
  const pollingIntervalRef = useRef<number | null>(null);

  // Load exchanges on mount
  useEffect(() => {
    const fetchExchanges = async () => {
      try {
        dispatch(actions.setLoadingExchanges(true));
        const exchangesData = await api.getExchanges();
        dispatch(actions.setExchanges(exchangesData));
      } catch (err) {
        dispatch(actions.setError('Failed to load exchanges'));
        console.error(err);
      } finally {
        dispatch(actions.setLoadingExchanges(false));
      }
    };

    fetchExchanges();
  }, []);

  // Load listings when filters change
  useEffect(() => {
    const fetchListings = async () => {
      dispatch(actions.setLoadingListings(true));
      try {
        const params: Record<string, string | number> = {};
        
        // Use either date range or days depending on mode
        if (state.isPaginationMode && state.startDate && state.endDate) {
          params.start_date = state.startDate;
          params.end_date = state.endDate;
        } else {
          params.days = state.days;
        }
        
        if (state.selectedExchange) {
          params.exchange_code = state.selectedExchange;
        }
        
        const listingsData = await api.getListings(params);
        
        dispatch(actions.setListings(listingsData));
        
        // Reset notification state when filters change
        dispatch(actions.setNewListings(false, 0));
      } catch (err) {
        dispatch(actions.setError('Failed to load listings'));
        console.error(err);
      } finally {
        dispatch(actions.setLoadingListings(false));
      }
    };

    fetchListings();
  }, [state.selectedExchange, state.days, state.startDate, state.endDate, state.isPaginationMode]);

  // Load statistics when days change
  useEffect(() => {
    const fetchStatistics = async () => {
      try {
        // Only fetch statistics with days parameter
        if (!state.isPaginationMode) {
          dispatch(actions.setLoadingStatistics(true));
          const statsData = await api.getStatistics(state.days);
          dispatch(actions.setStatistics(statsData));
        }
      } catch (err) {
        dispatch(actions.setError('Failed to load statistics'));
        console.error(err);
      } finally {
        dispatch(actions.setLoadingStatistics(false));
      }
    };

    fetchStatistics();
  }, [state.days, state.isPaginationMode]);

  // Setup polling for new listings
  useEffect(() => {
    // Function to fetch listings only for notification purposes
    const fetchListingsForNotification = async () => {
      try {
        const params: Record<string, string | number> = { days: state.days };
        if (state.selectedExchange) {
          params.exchange_code = state.selectedExchange;
        }
        
        const listingsData = await api.getListings(params);
        const currentCount = listingsData.length;
        
        // If this isn't the first check and we have more listings than before
        if (state.previousListingsCount > 0 && currentCount > state.previousListingsCount) {
          const newCount = currentCount - state.previousListingsCount;
          dispatch(actions.setNewListings(true, newCount));
          
          // Show browser notification if allowed
          if (Notification.permission === 'granted') {
            new Notification('New Financial Listings', {
              body: `${newCount} new listing${newCount > 1 ? 's' : ''} detected!`,
              icon: '/logo.png'
            });
          }
          
          // Update the listings without setting loading state
          dispatch(actions.setListings(listingsData));
        }
      } catch (err) {
        console.error('Background polling error:', err);
      }
    };

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
  }, [state.days, state.selectedExchange, state.previousListingsCount]);

  // Create context value
  const contextValue: AppContextType = {
    state,
    dispatch,
    actions,
  };

  return (
    <AppContext.Provider value={contextValue}>
      {children}
    </AppContext.Provider>
  );
};

// Custom hook to use the context
export const useAppContext = () => {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
};