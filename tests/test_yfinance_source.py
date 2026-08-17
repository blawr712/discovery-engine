from unittest.mock import patch
import unittest

import pandas as pd

from src.data_sources.yfinance_source import YFinanceSource


class YFinanceSourceTests(unittest.TestCase):
    @patch("src.data_sources.yfinance_source.yf.download")
    def test_requests_corporate_actions_with_adjusted_daily_history(self, download):
        download.return_value = pd.DataFrame()

        result = YFinanceSource().get_price_history("TEST")

        self.assertTrue(result.empty)
        download.assert_called_once_with(
            "TEST", period="1y", interval="1d", auto_adjust=True,
            actions=True, progress=False,
        )


if __name__ == "__main__":
    unittest.main()
