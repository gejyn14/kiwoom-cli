"""Shared lookup maps for CLI option value -> API value conversion."""

MARKET_ALL = {"all": "000", "kospi": "001", "kosdaq": "101"}
MARKET_TWO = {"kospi": "001", "kosdaq": "101"}
MARKET_KOSPI_KOSDAQ = {"kospi": "0", "kosdaq": "1"}
MARKET_PROGRAM = {"kospi": "P00101", "kosdaq": "P10102"}
MARKET_SEARCH = {"kospi": "0", "kosdaq": "10", "k-otc": "30", "konex": "50", "etf": "8", "elw": "3"}
EXCHANGE_TWO = {"KRX": "1", "NXT": "2"}
EXCHANGE_ALL = {"KRX": "1", "NXT": "2", "all": "3"}
# stex_tp with "all"=0 (used by ka10075/ka10076/ka10085); distinct from EXCHANGE_ALL where "all"=3.
EXCHANGE_ALL_ZERO = {"all": "0", "KRX": "1", "NXT": "2"}
