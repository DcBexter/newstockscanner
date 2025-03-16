from typing import Tuple, Optional

class HKEXUtils:
    """Utility class for HKEX-related functionality."""
    
    # URL parameters for different search scopes
    BASIC_SEARCH_SCOPE = "Market%20Data|Listing"
    EXPANDED_SEARCH_SCOPE = "Market%20Data|Products|Services|Listing|News|FAQ|Global"
    
    @staticmethod
    def get_listing_detail_url(symbol: str, name: str, status: str = None) -> Tuple[Optional[str], str]:
        """Get the listing detail URL and security type for a given symbol and name.
        For some securities (especially during corporate actions or new listings),
        no detail page may exist on the exchange website.
        
        Args:
            symbol: The stock symbol
            name: The stock name
            status: The stock status (optional)
            
        Returns:
            A tuple of (url, security_type) where url may be None if no detail page exists
        """
        clean_symbol = symbol.lstrip('0')  # Remove leading zeros
        
        # Define corporate actions that typically don't have detail pages
        no_page_actions = [
            'Share Consolidation',
            'Trading in the Nil Paid Rights',
            'Suspended',
            'Delisted',
            'Stock Split'
        ]
        
        # First determine the security type
        if 'Note' in name or 'Bond' in name or 'B28' in name:
            security_type = "Bond/Note"
        elif symbol.startswith('85'):
            security_type = "Futures/Options"
        elif 'RTS' in name:
            security_type = "Rights Issue"
        else:
            security_type = "Equity"
        
        # For corporate actions, use expanded search scope
        if status and any(action in status for action in no_page_actions):
            search_scope = HKEXUtils.EXPANDED_SEARCH_SCOPE
        else:
            # Use simpler URL for regular securities
            search_scope = HKEXUtils.BASIC_SEARCH_SCOPE
            
        base_url = f"https://www.hkex.com.hk/Global/HKEX-Market-Search-Result?sc_lang=en&q={clean_symbol}&sym={clean_symbol}&u={search_scope}"
        return (base_url, security_type) 
