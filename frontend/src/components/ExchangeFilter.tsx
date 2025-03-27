import type { Exchange } from '../api/client';
import { FormControl, InputLabel, MenuItem, Select } from '@mui/material';
import { SIZES } from '../theme';

/**
 * Props for the ExchangeFilter component
 */
interface ExchangeFilterProps {
  /** List of available exchanges to display in the dropdown */
  exchanges: Exchange[];
  /** Currently selected exchange code (empty string means "All Exchanges") */
  value: string;
  /** Callback function triggered when the user selects a different exchange */
  onChange: (value: string) => void;
}

/**
 * ExchangeFilter component
 *
 * Renders a dropdown menu that allows users to filter stock listings by exchange.
 * Includes an "All Exchanges" option and a list of available exchanges.
 *
 * @param props - Component props
 * @returns A FormControl component with a Select dropdown for exchanges
 */
export default function ExchangeFilter({ exchanges, value, onChange }: ExchangeFilterProps) {
  // Track if "All Exchanges" is selected to provide appropriate aria-label for accessibility
  const isAllExchanges = value === '';

  return (
    <FormControl sx={{ minWidth: SIZES.minWidth.formControl }}>
      <InputLabel>Exchange</InputLabel>
      <Select
        value={value}
        label="Exchange"
        onChange={event => onChange(event.target.value)}
        // Use aria-label with information about the current selection
        aria-label={isAllExchanges ? 'All exchanges selected' : 'Specific exchange selected'}
      >
        <MenuItem value="">All Exchanges</MenuItem>
        {exchanges.map(exchange => (
          <MenuItem key={exchange.code} value={exchange.code}>
            {exchange.name}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}
