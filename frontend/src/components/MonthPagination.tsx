import type { SelectChangeEvent } from "@mui/material";
import {
  CalendarMonth,
  ChevronLeft,
  ChevronRight,
  Today,
} from "@mui/icons-material";
import {
  Box,
  Button,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  useTheme,
} from "@mui/material";
import dayjs from "dayjs";
import { useCallback, useEffect, useState } from "react";

interface MonthPaginationProps {
  onMonthChange: (startDate: string, endDate: string) => void;

  onSwitchToDays: (days: number) => void;
  isPaginationMode: boolean;
}

export default function MonthPagination({
  onMonthChange,
  onSwitchToDays,
  isPaginationMode,
}: MonthPaginationProps) {
  const theme = useTheme();
  const [currentMonth, setCurrentMonth] = useState(dayjs());
  const [selectedDays, setSelectedDays] = useState<number>(30);

  // Helper function to call onMonthChange with properly formatted dates
  const updateDateRange = useCallback(
    (month: dayjs.Dayjs) => {
      const startDate = month.startOf("month").format("YYYY-MM-DD");
      const endDate = month.endOf("month").format("YYYY-MM-DD");
      onMonthChange(startDate, endDate);
    },
    [onMonthChange],
  );

  // Update parent component when month changes OR when switching to pagination mode
  useEffect(() => {
    if (isPaginationMode) {
      updateDateRange(currentMonth);
    }
  }, [currentMonth, isPaginationMode, updateDateRange]);

  // Go to previous month
  const handlePrevMonth = () => {
    // Create a new dayjs instance to avoid mutation issues
    const prevMonth = dayjs(currentMonth).subtract(1, "month");

    // Always update the date range directly when using month navigation
    updateDateRange(prevMonth);
    setCurrentMonth(prevMonth);
    // Switch dropdown to Monthly View
    setSelectedDays(0);
  };

  // Go to next month (don't allow future months)
  const handleNextMonth = () => {
    // Create a new dayjs instance to avoid mutation issues
    const nextMonth = dayjs(currentMonth).add(1, "month");
    const now = dayjs();

    // Compare year and month to prevent future date selection
    if (
      nextMonth.year() < now.year() ||
      (nextMonth.year() === now.year() && nextMonth.month() <= now.month())
    ) {
      // Always update the date range directly when using month navigation
      updateDateRange(nextMonth);
      setCurrentMonth(nextMonth);
      // Switch dropdown to Monthly View
      setSelectedDays(0);
    }
  };

  // Go to current month
  const handleCurrentMonth = () => {
    const now = dayjs();

    // Always update the date range directly when using month navigation
    updateDateRange(now);
    setCurrentMonth(now);
    // Switch dropdown to Monthly View
    setSelectedDays(0);
  };

  // Handle time range selection
  const handleTimeRangeChange = (event: SelectChangeEvent<number>) => {
    const days = event.target.value as number;
    setSelectedDays(days);

    if (days > 0) {
      // Switch to days mode
      onSwitchToDays(days);
    } else if (days === 0) {
      // Switch to current month mode
      handleCurrentMonth();
    }
  };

  // Check if next month button should be disabled
  const isNextMonthDisabled =
    currentMonth.month() === dayjs().month() &&
    currentMonth.year() === dayjs().year();

  // Get the time range text to display
  const getTimeRangeText = () => {
    if (!isPaginationMode && selectedDays > 0) {
      return `Last ${selectedDays} Days`;
    } else {
      return currentMonth.format("MMMM YYYY");
    }
  };

  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
      {/* Time range selector (combines both days and month options) */}
      <FormControl sx={{ minWidth: 200 }}>
        <InputLabel id="time-range-select-label">Time Range</InputLabel>
        <Select
          labelId="time-range-select-label"
          id="time-range-select"
          value={isPaginationMode ? 0 : selectedDays}
          onChange={handleTimeRangeChange}
          label="Time Range"
          sx={{ height: "56px" }}
        >
          <MenuItem value={0}>
            <Box
              sx={{
                display: "inline-flex",
                position: "relative",
                top: "2px",
                mr: 1,
              }}
            >
              <CalendarMonth fontSize="small" />
            </Box>
            Monthly View
          </MenuItem>
          <MenuItem value={7}>
            <Box
              sx={{
                display: "inline-flex",
                position: "relative",
                top: "2px",
                mr: 1,
              }}
            >
              <Today fontSize="small" />
            </Box>
            Last 7 Days
          </MenuItem>
          <MenuItem value={14}>
            <Box
              sx={{
                display: "inline-flex",
                position: "relative",
                top: "2px",
                mr: 1,
              }}
            >
              <Today fontSize="small" />
            </Box>
            Last 14 Days
          </MenuItem>
          <MenuItem value={30}>
            <Box
              sx={{
                display: "inline-flex",
                position: "relative",
                top: "2px",
                mr: 1,
              }}
            >
              <Today fontSize="small" />
            </Box>
            Last 30 Days
          </MenuItem>
          <MenuItem value={60}>
            <Box
              sx={{
                display: "inline-flex",
                position: "relative",
                top: "2px",
                mr: 1,
              }}
            >
              <Today fontSize="small" />
            </Box>
            Last 60 Days
          </MenuItem>
          <MenuItem value={90}>
            <Box
              sx={{
                display: "inline-flex",
                position: "relative",
                top: "2px",
                mr: 1,
              }}
            >
              <Today fontSize="small" />
            </Box>
            Last 90 Days
          </MenuItem>
        </Select>
      </FormControl>

      {/* Month navigation controls - always active */}
      <Box
        sx={{
          display: "inline-flex",
          alignItems: "center",
          border: `1px solid ${
            theme.palette.mode === "dark"
              ? "rgba(255, 255, 255, 0.23)"
              : "rgba(0, 0, 0, 0.23)"
          }`,
          borderRadius: "4px",
          boxSizing: "border-box",
          height: "56px",
          padding: 0,
          overflow: "hidden",
          backgroundColor: "transparent",
          position: "relative",
          minHeight: "56px",
        }}
      >
        <IconButton
          onClick={handlePrevMonth}
          sx={{
            borderRadius: 0,
            height: "56px",
            width: "40px",
            padding: 0,
            "&:hover": {
              backgroundColor: "rgba(0, 0, 0, 0.04)",
            },
            margin: 0,
          }}
        >
          <ChevronLeft fontSize="small" />
        </IconButton>

        <Button
          disableElevation
          disableRipple
          onClick={handleCurrentMonth}
          sx={{
            borderLeft: `1px solid ${
              theme.palette.mode === "dark"
                ? "rgba(255, 255, 255, 0.23)"
                : "rgba(0, 0, 0, 0.23)"
            }`,
            borderRight: `1px solid ${
              theme.palette.mode === "dark"
                ? "rgba(255, 255, 255, 0.23)"
                : "rgba(0, 0, 0, 0.23)"
            }`,
            borderRadius: 0,
            height: "56px",
            padding: "0 16px",
            minWidth: "140px",
            fontWeight: "bold",
            color: theme.palette.mode === "dark" ? "#1db954" : "#2e7d32",
            "&:hover": {
              backgroundColor: "rgba(0, 0, 0, 0.04)",
            },
            textTransform: "none",
            fontSize: "1rem",
          }}
        >
          {getTimeRangeText()}
        </Button>

        <IconButton
          onClick={handleNextMonth}
          disabled={isNextMonthDisabled}
          sx={{
            borderRadius: 0,
            height: "56px",
            width: "40px",
            padding: 0,
            "&:hover": {
              backgroundColor: "rgba(0, 0, 0, 0.04)",
            },
            margin: 0,
          }}
        >
          <ChevronRight fontSize="small" />
        </IconButton>
      </Box>
    </Box>
  );
}
