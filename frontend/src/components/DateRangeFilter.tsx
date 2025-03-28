import { FormControl, InputLabel, MenuItem, Select } from "@mui/material";
import { SIZES } from "../theme";

/**
 * Props for the DateRangeFilter component
 */
interface DateRangeFilterProps {
  /** Currently selected date range in days */
  value: number;
  /** Callback function triggered when the user selects a different date range */
  onChange: (value: number) => void;
}

/**
 * Predefined date range options for the dropdown
 */
const ranges = [
  { value: 7, label: "Last 7 days" },
  { value: 30, label: "Last 30 days" },
  { value: 90, label: "Last 90 days" },
  { value: 180, label: "Last 180 days" },
  { value: 365, label: "Last year" },
];

/**
 * DateRangeFilter component
 *
 * Renders a dropdown menu that allows users to filter stock listings by date range.
 * Provides predefined options for common time periods (7 days, 30 days, etc.).
 *
 * @param props - Component props
 * @param props.value - Currently selected date range in days
 * @param props.onChange - Callback function triggered when the user selects a different date range
 * @returns A FormControl component with a Select dropdown for date ranges
 */
export default function DateRangeFilter({
  value,
  onChange,
}: DateRangeFilterProps) {
  // Convert the numeric value to a human-readable label for the aria-label attribute
  // Falls back to 'Custom' if the value doesn't match any predefined range
  const foundRange = ranges.find((range) => range.value === value);
  const currentRangeLabel =
    foundRange !== undefined &&
    foundRange !== null &&
    foundRange.label !== undefined &&
    foundRange.label !== null &&
    foundRange.label !== ""
      ? foundRange.label
      : "Custom";

  return (
    <FormControl sx={{ minWidth: SIZES.minWidth.formControl }}>
      <InputLabel>Time Range</InputLabel>
      <Select
        value={value}
        label="Time Range"
        onChange={(event) => onChange(Number(event.target.value))}
        // Use aria-label with the current range label for accessibility
        aria-label={`Selected time range: ${currentRangeLabel}`}
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
