import { Snackbar, Alert, IconButton, Badge, Tooltip } from '@mui/material';
import { Notifications } from '@mui/icons-material';
import { useAppContext } from '../context/useAppContext';
import { NOTIFICATION_DURATION } from '../constants/exchanges';

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
      Notification.requestPermission().then(permission => {
        console.log(`Notification permission ${permission}`);
      });
    }
  };

  return (
    <>
      {/* Notification Icons */}
      {hasNewListings && (
        <Tooltip title={`${newListingsCount} new listing${newListingsCount > 1 ? 's' : ''} detected`}>
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
          {newListingsCount} new listing{newListingsCount > 1 ? 's' : ''} detected!
        </Alert>
      </Snackbar>
    </>
  );
}
