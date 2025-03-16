import { FormControl, InputLabel, MenuItem, Select } from '@mui/material';

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

export default function DateRangeFilter({
  value,
  onChange,
}: DateRangeFilterProps) {
  return (
    <FormControl sx={{ minWidth: 200 }}>
      <InputLabel>Time Range</InputLabel>
      <Select
        value={value}
        label="Time Range"
        onChange={(e) => onChange(Number(e.target.value))}
      >
        {ranges.map((range) => (
          <MenuItem key={range.value} value={range.value}>
            {range.label}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
} 