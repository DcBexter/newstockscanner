import { Box, useTheme } from '@mui/material';
import dayjs from 'dayjs';
import { useCallback } from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

interface StatisticsChartProps {
  data: {
    date: string;
    count: number;
  }[];
}

export function StatisticsChart({ data }: StatisticsChartProps) {
  const theme = useTheme();

  // Use useCallback to memoize the formatter functions
  const formatLabel = useCallback((date: string) => {
    return dayjs(date).format('YYYY-MM-DD');
  }, []);

  const formatTooltip = useCallback((value: number) => {
    return [value, 'Listings'] as [number, string];
  }, []);

  return (
    <Box
      sx={{
        width: '100%',
        height: 500,
      }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{
            top: 5,
            right: 30,
            left: 20,
            bottom: 5,
          }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
          <XAxis
            dataKey="date"
            tickFormatter={(date: string) => dayjs(date).format('MMM D')}
            stroke={theme.palette.text.secondary}
          />
          <YAxis stroke={theme.palette.text.secondary} />
          <Tooltip
            labelFormatter={formatLabel}
            formatter={formatTooltip}
            contentStyle={{
              backgroundColor: theme.palette.background.paper,
              borderColor: theme.palette.divider,
              color: theme.palette.text.primary,
            }}
          />
          <Line
            type="monotone"
            dataKey="count"
            stroke={theme.palette.primary.main}
            strokeWidth={2}
            activeDot={{ r: 8, fill: theme.palette.primary.main }}
            dot={{ fill: theme.palette.primary.main }}
          />
        </LineChart>
      </ResponsiveContainer>
    </Box>
  );
}

export default StatisticsChart;
