import { use } from 'react';
import { AppContext } from './AppContextTypes';

// Custom hook to use the context
export function useAppContext() {
  const context = use(AppContext);
  if (context === undefined) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
}
