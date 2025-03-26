import { AppState, AppAction, ActionType } from './types';

// Initial state
export const initialState: AppState = {
  // Data
  listings: [],
  exchanges: [],
  statistics: null,
  
  // Filters
  selectedExchange: '',
  days: 30,
  startDate: null,
  endDate: null,
  isPaginationMode: false,
  
  // UI state
  isLoadingListings: false,
  isLoadingExchanges: false,
  isLoadingStatistics: false,
  isScanning: false,
  showStatistics: true,
  
  // Error state
  error: null,
  
  // Notification state
  hasNewListings: false,
  notificationOpen: false,
  newListingsCount: 0,
  previousListingsCount: 0,
};

// Reducer function
export const reducer = (state: AppState, action: AppAction): AppState => {
  switch (action.type) {
    // Data actions
    case ActionType.SET_LISTINGS:
      return {
        ...state,
        listings: action.payload,
        previousListingsCount: state.listings.length,
      };
      
    case ActionType.SET_EXCHANGES:
      return {
        ...state,
        exchanges: action.payload,
      };
      
    case ActionType.SET_STATISTICS:
      return {
        ...state,
        statistics: action.payload,
      };
      
    // Filter actions
    case ActionType.SET_SELECTED_EXCHANGE:
      return {
        ...state,
        selectedExchange: action.payload,
      };
      
    case ActionType.SET_DAYS:
      return {
        ...state,
        days: action.payload,
        // Clear date range when switching to days mode
        isPaginationMode: false,
        startDate: null,
        endDate: null,
      };
      
    case ActionType.SET_DATE_RANGE:
      return {
        ...state,
        startDate: action.payload.startDate,
        endDate: action.payload.endDate,
        // Clear days when switching to date range mode
        isPaginationMode: true,
        days: 0,
      };
      
    case ActionType.SET_PAGINATION_MODE:
      return {
        ...state,
        isPaginationMode: action.payload,
      };
      
    // UI actions
    case ActionType.SET_LOADING_LISTINGS:
      return {
        ...state,
        isLoadingListings: action.payload,
      };
      
    case ActionType.SET_LOADING_EXCHANGES:
      return {
        ...state,
        isLoadingExchanges: action.payload,
      };
      
    case ActionType.SET_LOADING_STATISTICS:
      return {
        ...state,
        isLoadingStatistics: action.payload,
      };
      
    case ActionType.SET_SCANNING:
      return {
        ...state,
        isScanning: action.payload,
      };
      
    case ActionType.TOGGLE_STATISTICS:
      return {
        ...state,
        showStatistics: !state.showStatistics,
      };
      
    // Error actions
    case ActionType.SET_ERROR:
      return {
        ...state,
        error: action.payload,
      };
      
    case ActionType.CLEAR_ERROR:
      return {
        ...state,
        error: null,
      };
      
    // Notification actions
    case ActionType.SET_NEW_LISTINGS:
      return {
        ...state,
        hasNewListings: action.payload.hasNewListings,
        newListingsCount: action.payload.newListingsCount,
        notificationOpen: action.payload.hasNewListings,
      };
      
    case ActionType.SET_NOTIFICATION_OPEN:
      return {
        ...state,
        notificationOpen: action.payload,
      };
      
    case ActionType.ACKNOWLEDGE_NEW_LISTINGS:
      return {
        ...state,
        hasNewListings: false,
        notificationOpen: false,
      };
      
    default:
      return state;
  }
};