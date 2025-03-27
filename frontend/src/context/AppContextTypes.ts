import type * as actions from './actions';
import type { AppAction, AppState } from './types';
import { createContext } from 'react';

// Create context type
export interface AppContextType {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
  actions: typeof actions;
}

// Create context
export const AppContext = createContext<AppContextType | undefined>(undefined);
