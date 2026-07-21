from abc import ABC, abstractmethod


class MarketDataSource(ABC):
    @abstractmethod
    def get_stock_data(self, ticker: str) -> dict:
        pass

    @abstractmethod
    def get_price_history(self, ticker: str, period: str = "1y"):
        pass