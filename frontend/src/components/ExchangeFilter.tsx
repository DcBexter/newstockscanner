import { FormControl, InputLabel, MenuItem, Select } from '@mui/material';
import { Exchange } from '../api/client';

interface ExchangeFilterProps {
  exchanges: Exchange[];
  value: string;
  onChange: (value: string) => void;
}

export default function ExchangeFilter({
  exchanges,
  value,
  onChange,
}: ExchangeFilterProps) {
  return (
    <FormControl sx={{ minWidth: 200 }}>
      <InputLabel>Exchange</InputLabel>
      <Select
        value={value}
        label="Exchange"
        onChange={(event) => onChange(event.target.value)}
      >
        <MenuItem value="">All Exchanges</MenuItem>
        {exchanges.map((exchange) => (
          <MenuItem key={exchange.code} value={exchange.code}>
            {exchange.name}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
} 
