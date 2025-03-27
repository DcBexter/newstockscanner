import { FormControl, InputLabel, MenuItem, Select } from '@mui/material';
import { Exchange } from '../api/client';

/* eslint-disable no-unused-vars */
interface ExchangeFilterProps {
  exchanges: Exchange[];
  value: string;
  onChange: (value: string) => void;
}

export default function ExchangeFilter({ exchanges, value, onChange }: ExchangeFilterProps) {
  // Determine if "All Exchanges" is selected or a specific exchange
  const isAllExchanges = value === '';

  return (
    <FormControl sx={{ minWidth: 200 }}>
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
