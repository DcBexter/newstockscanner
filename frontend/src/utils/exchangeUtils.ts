import type { Exchange } from '../api/client';

/**
 * Find an exchange by code or name
 * @param exchanges List of exchanges to search
 * @param code Exchange code to match exactly
 * @param nameSubstring Substring to search for in exchange name
 * @returns The found exchange or undefined
 */
export function findExchange(
  exchanges: Exchange[],
  code: string,
  nameSubstring: string,
): Exchange | undefined {
  return exchanges.find(
    exchange =>
      exchange.code === code || exchange.name.toLowerCase().includes(nameSubstring.toLowerCase()),
  );
}

/**
 * Check if a specific exchange is selected
 * @param selectedExchange Currently selected exchange code or ID
 * @param exchange Exchange to check
 * @returns True if the exchange is selected
 */
export function isExchangeSelected(
  selectedExchange: string | null | undefined,
  exchange: Exchange | undefined,
): boolean {
  if (selectedExchange === null || selectedExchange === undefined || selectedExchange === '' || exchange === null || exchange === undefined)
    return false;
  return selectedExchange === exchange.code || selectedExchange === exchange.id.toString();
}

/**
 * Find common exchanges in the provided list
 * @param exchanges List of all exchanges
 * @returns Object containing references to common exchanges
 */
export function findCommonExchanges(exchanges: Exchange[]) {
  // Import from constants to avoid circular dependencies
  const EXCHANGE_CODES = {
    HKEX: 'HKEX',
    NASDAQ: 'NASDAQ',
    NYSE: 'NYSE',
  };

  return {
    hkexExchange: findExchange(exchanges, EXCHANGE_CODES.HKEX, 'hong kong'),
    nasdaqExchange: findExchange(exchanges, EXCHANGE_CODES.NASDAQ, 'nasdaq'),
    nyseExchange: findExchange(exchanges, EXCHANGE_CODES.NYSE, 'new york'),
  };
}
