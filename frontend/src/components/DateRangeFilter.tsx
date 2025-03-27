import { FormControl, InputLabel, MenuItem, Select } from '@mui/material';

/* eslint-disable no-unused-vars */
interface DateRangeFilterProps {
  value: number;
  onChange: (value: number) => void;
}

const ranges = [
  { value: 7, label: 'Last 7 days' },
  { value: 30, label: 'Last 30 days' },
  { value: 90, label: 'Last 90 days' },
  { value: 180, label: 'Last 180 days' },
  { value: 365, label: 'Last year' },
];

export default function DateRangeFilter({ value, onChange }: DateRangeFilterProps) {
  // Find the current range label based on value
  const currentRangeLabel = ranges.find(range => range.value === value)?.label || 'Custom';

  return (
    <FormControl sx={{ minWidth: 200 }}>
      <InputLabel>Time Range</InputLabel>
      <Select
        value={value}
        label="Time Range"
        onChange={event => onChange(Number(event.target.value))}
        // Use aria-label with the current range label for accessibility
        aria-label={`Selected time range: ${currentRangeLabel}`}
      >
        {ranges.map(range => (
          <MenuItem key={range.value} value={range.value}>
            {range.label}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}
