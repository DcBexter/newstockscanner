import { createContext } from 'react';
import { AppState, AppAction } from './types';
import * as actions from './actions';

// Create context type
export interface AppContextType {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
  actions: typeof actions;
}

// Create context
export const AppContext = createContext<AppContextType | undefined>(undefined);