/**
 * API configuration settings
 */

// Base API URL
export const API_URL = "/api/v1";

// Cache settings
export const CACHE_SETTINGS = {
  TTL: 1000, // 1 second cache TTL in milliseconds
  ENABLED: true,
};

// API endpoints
export const API_ENDPOINTS = {
  LISTINGS: "listings",
  EXCHANGES: "exchanges",
  STATISTICS: "statistics",
  SCRAPE: "scrape",
};

// Request timeouts
export const REQUEST_TIMEOUT = 30000; // 30 seconds
