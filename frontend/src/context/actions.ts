import { ActionType, AppAction } from './types';
import { Listing, Exchange, Statistics } from '../api/client';

// Data actions
export const setListings = (listings: Listing[]): AppAction => ({
  type: ActionType.SET_LISTINGS,
  payload: listings,
});

export const setExchanges = (exchanges: Exchange[]): AppAction => ({
  type: ActionType.SET_EXCHANGES,
  payload: exchanges,
});

export const setStatistics = (statistics: Statistics): AppAction => ({
  type: ActionType.SET_STATISTICS,
  payload: statistics,
});

// Filter actions
export const setSelectedExchange = (exchange: string): AppAction => ({
  type: ActionType.SET_SELECTED_EXCHANGE,
  payload: exchange,
});

export const setDays = (days: number): AppAction => ({
  type: ActionType.SET_DAYS,
  payload: days,
});

export const setDateRange = (startDate: string, endDate: string): AppAction => ({
  type: ActionType.SET_DATE_RANGE,
  payload: { startDate, endDate },
});

export const setPaginationMode = (isPaginationMode: boolean): AppAction => ({
  type: ActionType.SET_PAGINATION_MODE,
  payload: isPaginationMode,
});

// UI actions
export const setLoadingListings = (isLoading: boolean): AppAction => ({
  type: ActionType.SET_LOADING_LISTINGS,
  payload: isLoading,
});

export const setLoadingExchanges = (isLoading: boolean): AppAction => ({
  type: ActionType.SET_LOADING_EXCHANGES,
  payload: isLoading,
});

export const setLoadingStatistics = (isLoading: boolean): AppAction => ({
  type: ActionType.SET_LOADING_STATISTICS,
  payload: isLoading,
});

export const setScanning = (isScanning: boolean): AppAction => ({
  type: ActionType.SET_SCANNING,
  payload: isScanning,
});

export const toggleStatistics = (): AppAction => ({
  type: ActionType.TOGGLE_STATISTICS,
});

// Error actions
export const setError = (error: string): AppAction => ({
  type: ActionType.SET_ERROR,
  payload: error,
});

export const clearError = (): AppAction => ({
  type: ActionType.CLEAR_ERROR,
});

// Notification actions
export const setNewListings = (hasNewListings: boolean, newListingsCount: number): AppAction => ({
  type: ActionType.SET_NEW_LISTINGS,
  payload: { hasNewListings, newListingsCount },
});

export const setNotificationOpen = (isOpen: boolean): AppAction => ({
  type: ActionType.SET_NOTIFICATION_OPEN,
  payload: isOpen,
});

export const acknowledgeNewListings = (): AppAction => ({
  type: ActionType.ACKNOWLEDGE_NEW_LISTINGS,
});