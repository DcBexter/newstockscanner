import { Notifications } from '@mui/icons-material';
import { Alert, Badge, IconButton, Snackbar, Tooltip } from '@mui/material';
import { NOTIFICATION_DURATION } from '../constants/exchanges';
import { useAppContext } from '../context/useAppContext';

// Helper function for logging that only runs in development mode
function devLog(message: string): void {
  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console
    console.log(message);
  }
}

/**
 * Component for handling notifications and notification permissions
 */
export default function NotificationSection() {
  const { state, dispatch, actions } = useAppContext();
  const { hasNewListings, notificationOpen, newListingsCount } = state;

  /**
   * Handle notification close
   */
  const handleNotificationClose = () => {
    dispatch(actions.setNotificationOpen(false));
  };

  /**
   * Acknowledge new listings
   */
  const acknowledgeNewListings = () => {
    dispatch(actions.acknowledgeNewListings());
  };

  /**
   * Request notification permission
   */
  const requestNotificationPermission = () => {
    if (Notification.permission !== 'granted' && Notification.permission !== 'denied') {
      Notification.requestPermission()
        .then((permission) => {
          devLog(`Notification permission ${permission}`);
        })
        .catch((error) => {
          devLog(`Error requesting notification permission: ${error}`);
        });
    }
  };

  return (
    <>
      {/* Notification Icons */}
      {hasNewListings && (
        <Tooltip
          title={`${newListingsCount} new listing${newListingsCount > 1 ? 's' : ''} detected`}
        >
          <Badge badgeContent={newListingsCount} color="error" overlap="circular">
            <IconButton color="primary" onClick={acknowledgeNewListings}>
              <Notifications />
            </IconButton>
          </Badge>
        </Tooltip>
      )}

      {Notification.permission !== 'granted' && Notification.permission !== 'denied' && (
        <Tooltip title="Enable notifications">
          <IconButton color="primary" onClick={requestNotificationPermission}>
            <Notifications />
          </IconButton>
        </Tooltip>
      )}

      {/* New Listings Notification */}
      <Snackbar
        open={notificationOpen}
        autoHideDuration={NOTIFICATION_DURATION}
        onClose={handleNotificationClose}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Alert
          onClose={handleNotificationClose}
          severity="success"
          variant="filled"
          sx={{ width: '100%' }}
        >
          {newListingsCount}
          {' '}
          new listing
          {newListingsCount > 1 ? 's' : ''}
          {' '}
          detected!
        </Alert>
      </Snackbar>
    </>
  );
}
