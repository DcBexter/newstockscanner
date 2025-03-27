import type { ErrorInfo, ReactNode } from 'react';
import { Box, Button, Paper, Typography } from '@mui/material';
import { Component } from 'react';
import { COLORS, SPACING } from '../theme';

/**
 * Props for the ErrorBoundary component
 */
interface ErrorBoundaryProps {
  /** The child components that this boundary will protect */
  children: ReactNode;
  /** Optional custom fallback component to display when an error occurs */
  fallback?: ReactNode;
  /** Optional callback function that will be called when an error is caught */
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

/**
 * State for the ErrorBoundary component
 */
interface ErrorBoundaryState {
  /** Whether an error has been caught */
  hasError: boolean;
  /** The error that was caught, if any */
  error: Error | null;
  /** Additional information about the error */
  errorInfo: ErrorInfo | null;
}

/**
 * ErrorBoundary component
 *
 * A React error boundary that catches JavaScript errors anywhere in its child component tree,
 * logs those errors, and displays a fallback UI instead of crashing the whole application.
 *
 * @example
 * // Basic usage
 * <ErrorBoundary>
 *   <MyComponent />
 * </ErrorBoundary>
 *
 * @example
 * // With custom fallback UI
 * <ErrorBoundary fallback={<div>Something went wrong</div>}>
 *   <MyComponent />
 * </ErrorBoundary>
 *
 * @example
 * // With error callback
 * <ErrorBoundary onError={(error, errorInfo) => logErrorToService(error, errorInfo)}>
 *   <MyComponent />
 * </ErrorBoundary>
 */
class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  /**
   * Update state when an error occurs
   */
  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return {
      hasError: true,
      error,
    };
  }

  /**
   * Log the error and call the onError callback if provided
   */
  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log the error to the console in development mode
    if (import.meta.env.DEV) {
      console.error('Error caught by ErrorBoundary:', error, errorInfo);
    }

    // Update state with error info
    this.setState({ errorInfo });

    // Call the onError callback if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  /**
   * Reset the error state
   */
  handleReset = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render(): ReactNode {
    // If there's no error, render the children
    if (!this.state.hasError) {
      return this.props.children;
    }

    // If a custom fallback is provided, use it
    if (this.props.fallback !== undefined && this.props.fallback !== null) {
      return this.props.fallback;
    }

    // Otherwise, render the default fallback UI
    return (
      <Paper
        elevation={3}
        sx={{
          p: SPACING.md,
          m: SPACING.md,
          backgroundColor: COLORS.grey[100],
          borderLeft: `4px solid ${COLORS.error.main}`,
        }}
      >
        <Typography variant="h5" color="error" gutterBottom>
          Something went wrong
        </Typography>
        <Typography variant="body1" component="p" sx={{ mb: 2 }}>
          An error occurred in this part of the application. Try refreshing the page or contact support if the problem persists.
        </Typography>
        {import.meta.env.DEV && this.state.error && (
          <Box sx={{ mt: SPACING.md, p: SPACING.md, backgroundColor: COLORS.grey[200], borderRadius: 1, overflow: 'auto' }}>
            <Typography variant="subtitle2" fontFamily="monospace">
              {this.state.error.toString()}
            </Typography>
            {this.state.errorInfo && (
              <Typography variant="body2" fontFamily="monospace" sx={{ mt: SPACING.sm, whiteSpace: 'pre-wrap' }}>
                {this.state.errorInfo.componentStack}
              </Typography>
            )}
          </Box>
        )}
        <Button
          variant="contained"
          color="primary"
          onClick={this.handleReset}
          sx={{ mt: SPACING.md }}
        >
          Try Again
        </Button>
      </Paper>
    );
  }
}

export default ErrorBoundary;
