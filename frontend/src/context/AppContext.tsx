import type { AppContextType } from "./AppContextTypes";
import type { AppAction, AppState } from "./types";
import React, {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
} from "react";
import { api } from "../api/client";
import * as actions from "./actions";
import { AppContext } from "./AppContextTypes";
import { initialState, reducer } from "./reducer";

// Helper function for logging errors that only runs in development mode
function devError(error: unknown, message?: string): void {
  if (import.meta.env.DEV) {
    if (message !== undefined && message !== null && message !== "") {
      console.error(message, error);
    } else {
      console.error(error);
    }
  }
}

// Constants
const POLLING_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes in milliseconds

// Custom hooks for data fetching
function useFetchExchanges(dispatch: React.Dispatch<AppAction>) {
  useEffect(() => {
    const fetchExchanges = async () => {
      try {
        dispatch(actions.setLoadingExchanges(true));
        const exchangesData = await api.getExchanges();
        dispatch(actions.setExchanges(exchangesData));
      } catch (err) {
        dispatch(actions.setError("Failed to load exchanges"));
        devError(err);
      } finally {
        dispatch(actions.setLoadingExchanges(false));
      }
    };

    // Create a wrapper function to handle the promise
    const fetchData = () => {
      const promise = fetchExchanges();
      // Handle any uncaught errors
      promise.catch((err) => {
        devError(err, "Unhandled promise rejection in fetchExchanges:");
      });
    };

    fetchData();
  }, [dispatch]);
}

function useFetchListings(
  state: AppState,
  dispatch: React.Dispatch<AppAction>,
) {
  useEffect(() => {
    const fetchListings = async () => {
      dispatch(actions.setLoadingListings(true));
      try {
        const params = createListingParams({
          isPaginationMode: state.isPaginationMode,
          startDate: state.startDate,
          endDate: state.endDate,
          days: state.days,
          selectedExchange: state.selectedExchange,
        });
        const listingsData = await api.getListings(params);

        dispatch(actions.setListings(listingsData));

        // Reset notification state when filters change
        dispatch(actions.setNewListings(false, 0));
      } catch (err) {
        dispatch(actions.setError("Failed to load listings"));
        devError(err);
      } finally {
        dispatch(actions.setLoadingListings(false));
      }
    };

    // Create a wrapper function to handle the promise
    const fetchData = () => {
      const promise = fetchListings();
      // Handle any uncaught errors
      promise.catch((err) => {
        devError(err, "Unhandled promise rejection in fetchListings");
      });
    };

    fetchData();
  }, [
    state.isPaginationMode,
    state.startDate,
    state.endDate,
    state.days,
    state.selectedExchange,
    dispatch,
  ]);
}

function useFetchStatistics(
  state: AppState,
  dispatch: React.Dispatch<AppAction>,
) {
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
        dispatch(actions.setError("Failed to load statistics"));
        devError(err);
      } finally {
        dispatch(actions.setLoadingStatistics(false));
      }
    };

    // Create a wrapper function to handle the promise
    const fetchData = () => {
      const promise = fetchStatistics();
      // Handle any uncaught errors
      promise.catch((err) => {
        devError(err, "Unhandled promise rejection in fetchStatistics:");
      });
    };

    fetchData();
  }, [state.days, state.isPaginationMode, dispatch]);
}

function useListingPolling(
  state: AppState,
  dispatch: React.Dispatch<AppAction>,
) {
  const pollingIntervalRef = useRef<number | null>(null);

  const fetchListingsForNotification = useCallback(async () => {
    // Destructure the state properties we need to use
    const {
      days,
      startDate,
      endDate,
      isPaginationMode,
      selectedExchange,
      previousListingsCount,
    } = state;

    try {
      const params = createListingParams({
        days,
        startDate,
        endDate,
        isPaginationMode,
        selectedExchange,
      });
      const listingsData = await api.getListings(params);
      const currentCount = listingsData.length;

      // If this isn't the first check and we have more listings than before
      if (previousListingsCount > 0 && currentCount > previousListingsCount) {
        const newCount = currentCount - previousListingsCount;
        dispatch(actions.setNewListings(true, newCount));

        // Show browser notification if allowed
        if (Notification.permission === "granted") {
          // Use void to indicate intentional non-use of the notification object
          void new Notification("New Financial Listings", {
            body: `${newCount} new listing${newCount > 1 ? "s" : ""} detected!`,
            icon: "/logo.png",
          });
        }

        // Update the listings without setting loading state
        dispatch(actions.setListings(listingsData));
      }
    } catch (err) {
      devError(err, "Background polling error:");
    }
  }, [dispatch, state]);

  useEffect(() => {
    // Setup auto-polling for new listings
    if (
      pollingIntervalRef.current !== null &&
      pollingIntervalRef.current !== undefined &&
      pollingIntervalRef.current !== 0
    ) {
      window.clearInterval(pollingIntervalRef.current);
    }

    pollingIntervalRef.current = window.setInterval(() => {
      // Only poll if the user has granted notification permission
      if (Notification.permission === "granted") {
        // Handle the promise returned by fetchListingsForNotification
        const promise = fetchListingsForNotification();
        // Handle any uncaught errors
        promise.catch((err) => {
          devError(
            err,
            "Unhandled promise rejection in fetchListingsForNotification:",
          );
        });
      }
    }, POLLING_INTERVAL_MS);

    return () => {
      if (
        pollingIntervalRef.current !== null &&
        pollingIntervalRef.current !== undefined &&
        pollingIntervalRef.current !== 0
      ) {
        window.clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [
    state.days,
    state.selectedExchange,
    state.previousListingsCount,
    fetchListingsForNotification,
  ]);
}

// Helper function to create listing params
function createListingParams({
  isPaginationMode,
  startDate,
  endDate,
  days,
  selectedExchange,
}: {
  isPaginationMode: boolean;
  startDate: string | null;
  endDate: string | null;
  days: number;
  selectedExchange: string;
}): Record<string, string | number> {
  const params: Record<string, string | number> = {};

  // Use either date range or days depending on mode
  if (
    isPaginationMode &&
    startDate !== undefined &&
    startDate !== null &&
    startDate !== "" &&
    endDate !== undefined &&
    endDate !== null &&
    endDate !== ""
  ) {
    params.start_date = startDate;
    params.end_date = endDate;
  } else {
    params.days = days;
  }

  if (selectedExchange) {
    params.exchange_code = selectedExchange;
  }

  return params;
}

// Provider component
interface AppProviderProps {
  children: React.ReactNode;
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(reducer, initialState);

  // Use custom hooks for data fetching
  useFetchExchanges(dispatch);
  useFetchListings(state, dispatch);
  useFetchStatistics(state, dispatch);
  useListingPolling(state, dispatch);

  // Create memoized context value to prevent unnecessary re-renders
  const contextValue = useMemo<AppContextType>(
    () => ({
      state,
      dispatch,
      actions,
    }),
    [state],
  );

  return <AppContext value={contextValue}>{children}</AppContext>;
};
