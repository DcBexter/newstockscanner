import { Box, useTheme } from '@mui/material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import dayjs from 'dayjs';

interface StatisticsChartProps {
  data: {
    date: string;
    count: number;
  }[];
}

export function StatisticsChart({ data }: StatisticsChartProps) {
  const theme = useTheme();
  
  return (
    <Box sx={{ 
      width: '100%', 
      height: 500,
    }}>
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
            tickFormatter={(date) => dayjs(date).format('MMM D')}
            stroke={theme.palette.text.secondary}
          />
          <YAxis stroke={theme.palette.text.secondary} />
          <Tooltip
            labelFormatter={(date) => dayjs(date).format('YYYY-MM-DD')}
            formatter={(value) => [value, 'Listings']}
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