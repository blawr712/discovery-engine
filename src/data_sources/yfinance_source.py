import yfinance as yf
import pandas as pd

from .base import MarketDataSource


class YFinanceSource(MarketDataSource):
    def get_stock_data(self, ticker: str) -> dict:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        return {
            "ticker": ticker,
            "company_name": info.get("shortName") or info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency"),
            "exchange": info.get("exchange"),
            "country": self._infer_country(ticker),
        }

    def get_price_history(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        df = yf.download(
            ticker,
            period=period,
            interval="1d",
            auto_adjust=True,
            progress=False,
        )

        if df.empty:
            return pd.DataFrame()

        df = df.reset_index()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        return df

    @staticmethod
    def _infer_country(ticker: str) -> str:
        if ticker.endswith(".TO") or ticker.endswith(".V") or ticker.endswith(".CN"):
            return "CA"
        return "US"