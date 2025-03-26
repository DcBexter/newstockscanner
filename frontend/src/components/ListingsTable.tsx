import { useState, useEffect, useMemo } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Box,
  IconButton,
  Tooltip,
  Chip,
  TextField,
  InputAdornment,
  TableSortLabel,
  useTheme,
} from '@mui/material';
import LaunchIcon from '@mui/icons-material/Launch';
import InfoIcon from '@mui/icons-material/Info';
import LinkIcon from '@mui/icons-material/Link';
import { Listing } from '../api/client';
import dayjs from 'dayjs';
import localizedFormat from 'dayjs/plugin/localizedFormat';
import { Search } from '@mui/icons-material';

// Initialize dayjs plugins
dayjs.extend(localizedFormat);
// Set locale based on browser
dayjs.locale(navigator.language || 'en');

interface ListingsTableProps {
  data: Listing[];
  isLoading: boolean;
}

type SortDirection = 'asc' | 'desc';
type SortField = keyof Listing | '';

export default function ListingsTable({ data, isLoading }: ListingsTableProps) {
  const [sortField, setSortField] = useState<SortField>('listing_date');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [searchTerm, setSearchTerm] = useState('');
  const [filteredData, setFilteredData] = useState<Listing[]>([]);
  const theme = useTheme();

  // Clean data when props change
  useEffect(() => {
    // Ensure data is an array
    setFilteredData(Array.isArray(data) ? data : []);
  }, [data]);

  // Filter data when search term changes
  useEffect(() => {
    if (!searchTerm.trim()) {
      setFilteredData(Array.isArray(data) ? data : []);
      return;
    }

    const lowercasedTerm = searchTerm.toLowerCase();
    // Ensure data is an array before filtering
    const dataArray = Array.isArray(data) ? data : [];
    const results = dataArray.filter((item) => {
      return (
        (item.symbol && item.symbol.toLowerCase().includes(lowercasedTerm)) ||
        (item.name && item.name.toLowerCase().includes(lowercasedTerm)) ||
        (item.exchange_code && item.exchange_code.toLowerCase().includes(lowercasedTerm)) ||
        (item.security_type && item.security_type.toLowerCase().includes(lowercasedTerm))
      );
    });

    setFilteredData(results);
  }, [searchTerm, data]);

  // Handle sorting
  const handleSort = (field: SortField) => {
    const isAsc = sortField === field && sortDirection === 'asc';
    setSortDirection(isAsc ? 'desc' : 'asc');
    setSortField(field);
  };

  // Sort data based on current sort settings
  const sortedData = useMemo(() => {
    if (!sortField) return filteredData || [];

    // Ensure filteredData is an array before spreading
    const dataToSort = Array.isArray(filteredData) ? filteredData : [];
    return [...dataToSort].sort((a, b) => {
      const aValue = a[sortField];
      const bValue = b[sortField];

      // Handle various data types
      if (typeof aValue === 'string' && typeof bValue === 'string') {
        return sortDirection === 'asc' 
          ? aValue.localeCompare(bValue) 
          : bValue.localeCompare(aValue);
      }

      // Handle numeric values
      if (aValue !== undefined && bValue !== undefined) {
        return sortDirection === 'asc' 
          ? (aValue > bValue ? 1 : -1) 
          : (bValue > aValue ? 1 : -1);
      }

      // Handle undefined values
      if (aValue === undefined) return sortDirection === 'asc' ? -1 : 1;
      if (bValue === undefined) return sortDirection === 'asc' ? 1 : -1;

      // Fallback
      return 0;
    });
  }, [filteredData, sortField, sortDirection]);

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress color="primary" />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ mb: 2 }}>
        <TextField
          fullWidth
          size="small"
          placeholder="Search by name, symbol, exchange, or type..."
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <Search />
                </InputAdornment>
              ),
            }
          }}
        />
      </Box>

      <TableContainer 
        className="table-container" 
        sx={{ 
          backgroundColor: theme.palette.background.paper,
          borderRadius: 1,
          '& .MuiTableCell-root': {
            borderBottom: `1px solid ${theme.palette.divider}`,
            fontSize: '1.1rem',
            padding: '12px 16px',
          },
        }}
      >
        <Table>
          <TableHead>
            <TableRow sx={{ backgroundColor: theme.palette.mode === 'dark' ? '#1e1e1e' : '#f5f5f5' }}>
              <TableCell>
                <TableSortLabel
                  active={sortField === 'name'}
                  direction={sortField === 'name' ? sortDirection : 'asc'}
                  onClick={() => handleSort('name')}
                  sx={{ fontWeight: 'bold' }}
                >
                  Name
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortField === 'symbol'}
                  direction={sortField === 'symbol' ? sortDirection : 'asc'}
                  onClick={() => handleSort('symbol')}
                  sx={{ fontWeight: 'bold' }}
                >
                  Symbol
                </TableSortLabel>
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortField === 'exchange_code'}
                  direction={sortField === 'exchange_code' ? sortDirection : 'asc'}
                  onClick={() => handleSort('exchange_code')}
                  sx={{ fontWeight: 'bold' }}
                >
                  Exchange
                </TableSortLabel>
              </TableCell>
              <TableCell sx={{ fontWeight: 'bold' }}>Type</TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortField === 'listing_date'}
                  direction={sortField === 'listing_date' ? sortDirection : 'asc'}
                  onClick={() => handleSort('listing_date')}
                  sx={{ fontWeight: 'bold' }}
                >
                  Listing Date
                </TableSortLabel>
              </TableCell>
              <TableCell align="right">
                <TableSortLabel
                  active={sortField === 'lot_size'}
                  direction={sortField === 'lot_size' ? sortDirection : 'asc'}
                  onClick={() => handleSort('lot_size')}
                  sx={{ fontWeight: 'bold' }}
                >
                  Lot Size
                </TableSortLabel>
              </TableCell>
              <TableCell sx={{ fontWeight: 'bold' }}>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sortedData.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  No listings found
                </TableCell>
              </TableRow>
            ) : (
              sortedData.map((listing, index) => (
                <TableRow 
                  key={listing.id || `${listing.exchange_code}-${listing.symbol}` || index}
                  hover
                  sx={{ 
                    '&:hover': { 
                      backgroundColor: theme.palette.action.hover
                    }
                  }}
                >
                  <TableCell>{listing.name || 'N/A'}</TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Box component="span" color="primary.main" mr={1}>
                        {listing.symbol || 'N/A'}
                      </Box>

                      {listing.url && (
                        <Tooltip title="Company Information">
                          <IconButton
                            href={listing.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            size="small"
                            color="primary"
                            sx={{ ml: 0.5 }}
                          >
                            {listing.url.toLowerCase().endsWith('.pdf') ? 
                              <InfoIcon fontSize="small" /> : 
                              <LinkIcon fontSize="small" />
                            }
                          </IconButton>
                        </Tooltip>
                      )}

                      {listing.listing_detail_url && (
                        <Tooltip title="Listing Details">
                          <IconButton
                            href={listing.listing_detail_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            size="small"
                            color="primary"
                            sx={{ ml: 0.5 }}
                          >
                            <LaunchIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Chip 
                      label={listing.exchange_code || 'Unknown'}
                      size="small"
                      variant="outlined"
                      sx={{ 
                        fontWeight: 'medium',
                        color: theme.palette.primary.main,
                        borderColor: theme.palette.primary.main,
                      }} 
                    />
                  </TableCell>
                  <TableCell>
                    <Chip 
                      label={listing.security_type || 'Equity'} 
                      size="small" 
                      sx={{ 
                        backgroundColor: theme.palette.mode === 'dark' ? 'rgba(58, 65, 111, 0.2)' : 'rgba(58, 65, 111, 0.1)', 
                        borderColor: 'divider',
                        color: 'text.primary',
                      }}
                    />
                  </TableCell>
                  <TableCell>
                    {listing.listing_date ? dayjs(listing.listing_date).format('ll') : 'N/A'}
                  </TableCell>
                  <TableCell align="right">{listing.lot_size || 'N/A'}</TableCell>
                  <TableCell>
                    {listing.status === 'Trading' || listing.status?.includes('Trading') ? (
                      <Box component="span" color="success.main">{listing.status}</Box>
                    ) : (
                      listing.status
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
} 
