import axios from 'axios';
import { API_URL, CACHE_SETTINGS, API_ENDPOINTS } from '../config/api.config';

// Simple cache implementation
interface CacheEntry {
  data: any;
  timestamp: number;
  params?: string;
}

const cache: Record<string, CacheEntry> = {};
// Use cache TTL from configuration
const CACHE_TTL = CACHE_SETTINGS.TTL;

// Helper to get cache key
const getCacheKey = (endpoint: string, params?: any): string => {
  const paramsString = params ? JSON.stringify(params) : '';
  return `${endpoint}:${paramsString}`;
};

// Helper to check if cache is valid
const isCacheValid = (cacheKey: string): boolean => {
  const entry = cache[cacheKey];
  if (!entry) return false;

  const now = Date.now();
  return now - entry.timestamp < CACHE_TTL;
};

export interface Listing {
  id: number;
  name: string;
  symbol: string;
  listing_date: string;
  lot_size: number;
  status: string;
  exchange_id: number;
  exchange_code?: string;
  url?: string;
  listing_detail_url?: string;
  security_type: string;
}

export interface Exchange {
  id: number;
  name: string;
  code: string;
  url: string;
}

export interface Statistics {
  exchange_stats: {
    name: string;
    code: string;
    total_listings: number;
  }[];
  daily_stats: {
    date: string;
    count: number;
  }[];
}

export interface PaginatedListings {
  items: Listing[];
  total: number;
  skip: number;
  limit: number;
}

export const api = {
  getListings: async (params?: {
    exchange_code?: string;
    days?: number;
    start_date?: string;
    end_date?: string;
  }) => {
    const cacheKey = getCacheKey(API_ENDPOINTS.LISTINGS, params);

    // Check cache first
    if (isCacheValid(cacheKey)) {
      console.log('Using cached listings data');
      return cache[cacheKey].data;
    }

    // If not in cache or expired, make the API call
    const { data } = await axios.get<PaginatedListings>(`${API_URL}/${API_ENDPOINTS.LISTINGS}/`, { params });

    // Store in cache
    cache[cacheKey] = {
      data: data.items,
      timestamp: Date.now(),
      params: JSON.stringify(params)
    };

    return data.items;
  },

  getExchanges: async () => {
    const cacheKey = getCacheKey(API_ENDPOINTS.EXCHANGES);

    // Check cache first
    if (isCacheValid(cacheKey)) {
      console.log('Using cached exchanges data');
      return cache[cacheKey].data;
    }

    // If not in cache or expired, make the API call
    const { data } = await axios.get<Exchange[]>(`${API_URL}/${API_ENDPOINTS.EXCHANGES}/`);

    // Store in cache
    cache[cacheKey] = {
      data,
      timestamp: Date.now()
    };

    return data;
  },

  getStatistics: async (days: number = 30) => {
    const cacheKey = getCacheKey(API_ENDPOINTS.STATISTICS, { days });

    // Check cache first
    if (isCacheValid(cacheKey)) {
      console.log('Using cached statistics data');
      return cache[cacheKey].data;
    }

    // If not in cache or expired, make the API call
    const { data } = await axios.get<Statistics>(`${API_URL}/${API_ENDPOINTS.STATISTICS}/`, {
      params: { days },
    });

    // Store in cache
    cache[cacheKey] = {
      data,
      timestamp: Date.now(),
      params: JSON.stringify({ days })
    };

    return data;
  },

  triggerScrape: async (exchange?: string) => {
    const { data } = await axios.post(`${API_URL}/${API_ENDPOINTS.SCRAPE}/`, null, {
      params: exchange ? { exchange } : undefined
    });
    return data;
  }
}; 
