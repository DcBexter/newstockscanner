import type { Exchange, Listing, Statistics } from "../api/client";
import type { AppAction } from "./types";
import { ActionType } from "./types";

// Data actions
export function setListings(listings: Listing[]): AppAction {
  return {
    type: ActionType.SET_LISTINGS,
    payload: listings,
  };
}

export function setExchanges(exchanges: Exchange[]): AppAction {
  return {
    type: ActionType.SET_EXCHANGES,
    payload: exchanges,
  };
}

export function setStatistics(statistics: Statistics): AppAction {
  return {
    type: ActionType.SET_STATISTICS,
    payload: statistics,
  };
}

// Filter actions
export function setSelectedExchange(exchange: string): AppAction {
  return {
    type: ActionType.SET_SELECTED_EXCHANGE,
    payload: exchange,
  };
}

export function setDays(days: number): AppAction {
  return {
    type: ActionType.SET_DAYS,
    payload: days,
  };
}

export function setDateRange(startDate: string, endDate: string): AppAction {
  return {
    type: ActionType.SET_DATE_RANGE,
    payload: { startDate, endDate },
  };
}

export function setPaginationMode(isPaginationMode: boolean): AppAction {
  return {
    type: ActionType.SET_PAGINATION_MODE,
    payload: isPaginationMode,
  };
}

// UI actions
export function setLoadingListings(isLoading: boolean): AppAction {
  return {
    type: ActionType.SET_LOADING_LISTINGS,
    payload: isLoading,
  };
}

export function setLoadingExchanges(isLoading: boolean): AppAction {
  return {
    type: ActionType.SET_LOADING_EXCHANGES,
    payload: isLoading,
  };
}

export function setLoadingStatistics(isLoading: boolean): AppAction {
  return {
    type: ActionType.SET_LOADING_STATISTICS,
    payload: isLoading,
  };
}

export function setScanning(isScanning: boolean): AppAction {
  return {
    type: ActionType.SET_SCANNING,
    payload: isScanning,
  };
}

export function toggleStatistics(): AppAction {
  return {
    type: ActionType.TOGGLE_STATISTICS,
  };
}

// Error actions
export function setError(error: string): AppAction {
  return {
    type: ActionType.SET_ERROR,
    payload: error,
  };
}

export function clearError(): AppAction {
  return {
    type: ActionType.CLEAR_ERROR,
  };
}

// Notification actions
export function setNewListings(
  hasNewListings: boolean,
  newListingsCount: number,
): AppAction {
  return {
    type: ActionType.SET_NEW_LISTINGS,
    payload: { hasNewListings, newListingsCount },
  };
}

export function setNotificationOpen(isOpen: boolean): AppAction {
  return {
    type: ActionType.SET_NOTIFICATION_OPEN,
    payload: isOpen,
  };
}

export function acknowledgeNewListings(): AppAction {
  return {
    type: ActionType.ACKNOWLEDGE_NEW_LISTINGS,
  };
}
