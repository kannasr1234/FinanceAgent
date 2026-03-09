import yfinance as yf
import logging

class StockService:
    def __init__(self):
        self.cache = {}

    def fetch_stock_data(self, symbol):
        if symbol in self.cache:
            logging.info(f'Fetching cached data for {symbol}')
            return self.cache[symbol]

        logging.info(f'Fetching new data for {symbol}')
        stock_data = yf.download(symbol)
        self.cache[symbol] = stock_data
        return stock_data
