import { Listing, Exchange, Statistics } from '../api/client';

// State types
export interface AppState {
  // Data
  listings: Listing[];
  exchanges: Exchange[];
  statistics: Statistics | null;
  
  // Filters
  selectedExchange: string;
  days: number;
  startDate: string | null;
  endDate: string | null;
  isPaginationMode: boolean;
  
  // UI state
  isLoadingListings: boolean;
  isLoadingExchanges: boolean;
  isLoadingStatistics: boolean;
  isScanning: boolean;
  showStatistics: boolean;
  
  // Error state
  error: string | null;
  
  // Notification state
  hasNewListings: boolean;
  notificationOpen: boolean;
  newListingsCount: number;
  previousListingsCount: number;
}

// Action types
export enum ActionType {
  // Data actions
  SET_LISTINGS = 'SET_LISTINGS',
  SET_EXCHANGES = 'SET_EXCHANGES',
  SET_STATISTICS = 'SET_STATISTICS',
  
  // Filter actions
  SET_SELECTED_EXCHANGE = 'SET_SELECTED_EXCHANGE',
  SET_DAYS = 'SET_DAYS',
  SET_DATE_RANGE = 'SET_DATE_RANGE',
  SET_PAGINATION_MODE = 'SET_PAGINATION_MODE',
  
  // UI actions
  SET_LOADING_LISTINGS = 'SET_LOADING_LISTINGS',
  SET_LOADING_EXCHANGES = 'SET_LOADING_EXCHANGES',
  SET_LOADING_STATISTICS = 'SET_LOADING_STATISTICS',
  SET_SCANNING = 'SET_SCANNING',
  TOGGLE_STATISTICS = 'TOGGLE_STATISTICS',
  
  // Error actions
  SET_ERROR = 'SET_ERROR',
  CLEAR_ERROR = 'CLEAR_ERROR',
  
  // Notification actions
  SET_NEW_LISTINGS = 'SET_NEW_LISTINGS',
  SET_NOTIFICATION_OPEN = 'SET_NOTIFICATION_OPEN',
  ACKNOWLEDGE_NEW_LISTINGS = 'ACKNOWLEDGE_NEW_LISTINGS',
}

// Action interfaces
export interface SetListingsAction {
  type: ActionType.SET_LISTINGS;
  payload: Listing[];
}

export interface SetExchangesAction {
  type: ActionType.SET_EXCHANGES;
  payload: Exchange[];
}

export interface SetStatisticsAction {
  type: ActionType.SET_STATISTICS;
  payload: Statistics;
}

export interface SetSelectedExchangeAction {
  type: ActionType.SET_SELECTED_EXCHANGE;
  payload: string;
}

export interface SetDaysAction {
  type: ActionType.SET_DAYS;
  payload: number;
}

export interface SetDateRangeAction {
  type: ActionType.SET_DATE_RANGE;
  payload: { startDate: string; endDate: string };
}

export interface SetPaginationModeAction {
  type: ActionType.SET_PAGINATION_MODE;
  payload: boolean;
}

export interface SetLoadingListingsAction {
  type: ActionType.SET_LOADING_LISTINGS;
  payload: boolean;
}

export interface SetLoadingExchangesAction {
  type: ActionType.SET_LOADING_EXCHANGES;
  payload: boolean;
}

export interface SetLoadingStatisticsAction {
  type: ActionType.SET_LOADING_STATISTICS;
  payload: boolean;
}

export interface SetScanningAction {
  type: ActionType.SET_SCANNING;
  payload: boolean;
}

export interface ToggleStatisticsAction {
  type: ActionType.TOGGLE_STATISTICS;
}

export interface SetErrorAction {
  type: ActionType.SET_ERROR;
  payload: string;
}

export interface ClearErrorAction {
  type: ActionType.CLEAR_ERROR;
}

export interface SetNewListingsAction {
  type: ActionType.SET_NEW_LISTINGS;
  payload: { hasNewListings: boolean; newListingsCount: number };
}

export interface SetNotificationOpenAction {
  type: ActionType.SET_NOTIFICATION_OPEN;
  payload: boolean;
}

export interface AcknowledgeNewListingsAction {
  type: ActionType.ACKNOWLEDGE_NEW_LISTINGS;
}

export type AppAction =
  | SetListingsAction
  | SetExchangesAction
  | SetStatisticsAction
  | SetSelectedExchangeAction
  | SetDaysAction
  | SetDateRangeAction
  | SetPaginationModeAction
  | SetLoadingListingsAction
  | SetLoadingExchangesAction
  | SetLoadingStatisticsAction
  | SetScanningAction
  | ToggleStatisticsAction
  | SetErrorAction
  | ClearErrorAction
  | SetNewListingsAction
  | SetNotificationOpenAction
  | AcknowledgeNewListingsAction;