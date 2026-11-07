from html.parser import HTMLParser
from unittest.mock import patch

import pytest

from mf_tracker.web.presentation import fund_category


@pytest.mark.parametrize("name,key,label", [
    ("Motilal Oswal Midcap Fund", "midcap", "Midcap"),
    ("Edelweiss Mid Cap Fund", "midcap", "Midcap"),
    ("HDFC Mid-Cap Opportunities", "midcap", "Midcap"),
    ("MID CAP Fund", "midcap", "Midcap"),
    ("Invesco Smallcap Fund", "smallcap", "Smallcap"),
    ("Quant Small Cap Fund", "smallcap", "Smallcap"),
    ("Small-Cap Fund", "smallcap", "Smallcap"),
    ("Parag Parikh Flexi Cap Fund", "flexicap", "Flexi Cap"),
    ("Flexi-Cap Fund", "flexicap", "Flexi Cap"),
    ("Quant ELSS Tax Saver Fund", "elss", "ELSS"),
    ("Nifty Microcap 250 Index Fund", "microcap", "Microcap"),
    ("Micro Cap Fund", "microcap", "Microcap"),
    ("Micro-Cap Fund", "microcap", "Microcap"),
    ("Midcapital Fund", "other", "Other"),
    ("Unknown Fund", "other", "Other"),
    ("", "other", "Other"),
    (None, "other", "Other"),
])
def test_fund_category(name, key, label):
    assert fund_category(name) == {"key": key, "label": label}


def portfolio_payload():
    names = ["Beta Midcap Fund", "Alpha Mid-Cap Fund", "Missing Mid Cap Fund",
             "Beta Smallcap Fund", "Alpha Small Cap Fund", "Flexi Cap Fund",
             "ELSS Fund", "Microcap Fund", "Unknown Fund", "Research Midcap Fund"]
    funds = []
    periods = ["1day", "1week", "1month", "3month", "6month", "1year", "2year", "3year", "5year"]
    for i, name in enumerate(names):
        breakdown = {}
        if i != 2:
            for years in (2, 3, 5):
                breakdown[f"{years}year"] = {
                    **{f"year{y}": float(i + y) for y in range(1, years + 1)},
                    "total_absolute": float(i + 20), "year_dates": {},
                }
        funds.append({
            "name": name, "code": str(100000 + i), "current_nav": 100.0,
            "returns": {period: None if i == 2 else float(i - 3) for period in periods},
            "year_breakdown": breakdown, "is_portfolio": i != 9,
            "consistency_score": 50.0, "data_completeness": 1.0,
        })
    return {"funds": funds, "comparison_anchor_date": "06-11-2026", "comparison_header_dates": {}}


class PortfolioRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.categories = []
        self.buttons = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr" and "data-portfolio-fund" in attrs:
            self.categories.append(attrs["data-category"])
        if "data-portfolio-category" in attrs:
            self.buttons.append(attrs["data-portfolio-category"])


def test_index_labels_all_four_portfolio_tables(client):
    with patch("mf_tracker.web.views.get_cached_data", return_value=portfolio_payload()):
        response = client.get("/")
    assert response.status_code == 200
    parser = PortfolioRows()
    parser.feed(response.get_data(as_text=True))
    expected = ["midcap"] * 3 + ["smallcap"] * 2 + ["flexicap", "elss", "microcap", "other"]
    assert parser.categories == expected * 4
    assert parser.buttons == ["all", "midcap", "smallcap"]
