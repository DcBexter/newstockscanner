import axios from 'axios';
import { API_ENDPOINTS, API_URL, CACHE_SETTINGS } from '../config/api.config';

// Helper function for logging that only runs in development mode
function devLog(message: string): void {
  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console
    console.log(message);
  }
}

/**
 * API Client for the Stock Scanner Application
 *
 * Note on naming conventions:
 * - The backend API uses snake_case for all field names and parameters
 * - The frontend uses camelCase for variables and functions
 * - For API communication, we maintain snake_case in interfaces and parameters
 *   that directly interact with the API to match the backend convention
 * - This approach avoids the need for conversion between naming conventions
 *   but requires careful attention when working with API data
 */

// Simple cache implementation
interface CacheEntry<T> {
  data: T;
  timestamp: number;
  params?: string;
}

const cache: Record<string, CacheEntry<unknown>> = {};
// Use cache TTL from configuration
const CACHE_TTL = CACHE_SETTINGS.TTL;

// Helper to get cache key
function getCacheKey(endpoint: string, params?: Record<string, unknown>): string {
  const paramsString = params ? JSON.stringify(params) : '';
  return `${endpoint}:${paramsString}`;
}

// Helper to check if cache is valid
function isCacheValid(cacheKey: string): boolean {
  const entry = cache[cacheKey];
  if (entry === undefined || entry === null)
    return false;

  const now = Date.now();
  return now - entry.timestamp < CACHE_TTL;
}

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
  }): Promise<Listing[]> => {
    const cacheKey = getCacheKey(API_ENDPOINTS.LISTINGS, params);

    // Check cache first
    if (isCacheValid(cacheKey)) {
      devLog('Using cached listings data');
      return cache[cacheKey].data as Listing[];
    }

    // If not in cache or expired, make the API call
    const { data } = await axios.get<PaginatedListings>(`${API_URL}/${API_ENDPOINTS.LISTINGS}/`, {
      params,
    });

    // Store in cache
    cache[cacheKey] = {
      data: data.items,
      timestamp: Date.now(),
      params: JSON.stringify(params),
    } as CacheEntry<Listing[]>;

    return data.items;
  },

  getExchanges: async (): Promise<Exchange[]> => {
    const cacheKey = getCacheKey(API_ENDPOINTS.EXCHANGES);

    // Check cache first
    if (isCacheValid(cacheKey)) {
      devLog('Using cached exchanges data');
      return cache[cacheKey].data as Exchange[];
    }

    // If not in cache or expired, make the API call
    const { data } = await axios.get<Exchange[]>(`${API_URL}/${API_ENDPOINTS.EXCHANGES}/`);

    // Store in cache
    cache[cacheKey] = {
      data,
      timestamp: Date.now(),
    } as CacheEntry<Exchange[]>;

    return data;
  },

  getStatistics: async (days: number = 30): Promise<Statistics> => {
    const cacheKey = getCacheKey(API_ENDPOINTS.STATISTICS, { days });

    // Check cache first
    if (isCacheValid(cacheKey)) {
      devLog('Using cached statistics data');
      return cache[cacheKey].data as Statistics;
    }

    // If not in cache or expired, make the API call
    const { data } = await axios.get<Statistics>(`${API_URL}/${API_ENDPOINTS.STATISTICS}/`, {
      params: { days },
    });

    // Store in cache
    cache[cacheKey] = {
      data,
      timestamp: Date.now(),
      params: JSON.stringify({ days }),
    } as CacheEntry<Statistics>;

    return data;
  },

  triggerScrape: async (exchange?: string): Promise<unknown> => {
    // Explicitly type the response to avoid unsafe assignment
    const response: { data: unknown; } = await axios.post(`${API_URL}/${API_ENDPOINTS.SCRAPE}/`, null, {
      params: exchange !== undefined && exchange !== null && exchange !== '' ? { exchange } : undefined,
    });
    return response.data;
  },
};
