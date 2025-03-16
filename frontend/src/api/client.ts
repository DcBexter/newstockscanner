import axios from 'axios';

const API_URL = '/api/v1';

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

export const api = {
  getListings: async (params?: {
    exchange_code?: string;
    days?: number;
    start_date?: string;
    end_date?: string;
  }) => {
    const { data } = await axios.get<Listing[]>(`${API_URL}/listings/`, { params });
    return data;
  },

  getExchanges: async () => {
    const { data } = await axios.get<Exchange[]>(`${API_URL}/exchanges/`);
    return data;
  },

  getStatistics: async (days: number = 30) => {
    const { data } = await axios.get<Statistics>(`${API_URL}/statistics/`, {
      params: { days },
    });
    return data;
  },

  triggerScrape: async (exchange?: string) => {
    const { data } = await axios.post(`${API_URL}/scrape/`, null, {
      params: exchange ? { exchange } : undefined
    });
    return data;
  }
}; 