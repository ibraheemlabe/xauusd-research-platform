"""
tests/test_cot_parser.py
Verifies COT CSV parsing and net position calculation.
"""

import io
import pandas as pd
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.fetchers.cftc_cot import parse_cot_upload, _empty_cot


def _make_cot_csv(rows: list[dict]) -> io.BytesIO:
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf


def test_parse_cot_upload_basic():
    rows = [
        {
            "As_of_Date_In_Form_YYMMDD": "240101",
            "CFTC_Commodity_Code": "088691",
            "M_Money_Positions_Long_All": 150_000,
            "M_Money_Positions_Short_All": 50_000,
        },
        {
            "As_of_Date_In_Form_YYMMDD": "240108",
            "CFTC_Commodity_Code": "088691",
            "M_Money_Positions_Long_All": 160_000,
            "M_Money_Positions_Short_All": 40_000,
        },
    ]
    buf = _make_cot_csv(rows)
    result = parse_cot_upload(buf)

    assert not result.empty, "Should parse rows successfully"
    assert "mm_net" in result.columns
    assert "mm_long" in result.columns
    assert "mm_short" in result.columns

    # Net = long - short
    assert int(result["mm_net"].iloc[0]) == 100_000
    assert int(result["mm_net"].iloc[1]) == 120_000


def test_parse_cot_upload_net_can_be_negative():
    rows = [
        {
            "As_of_Date_In_Form_YYMMDD": "240101",
            "CFTC_Commodity_Code": "088691",
            "M_Money_Positions_Long_All": 30_000,
            "M_Money_Positions_Short_All": 80_000,
        },
    ]
    buf = _make_cot_csv(rows)
    result = parse_cot_upload(buf)
    assert int(result["mm_net"].iloc[0]) == -50_000


def test_parse_cot_upload_empty_file():
    buf = io.BytesIO(b"")
    result = parse_cot_upload(buf)
    # Should return some DataFrame (possibly empty) without raising
    assert isinstance(result, pd.DataFrame)


def test_empty_cot_shape():
    df = _empty_cot()
    assert list(df.columns) == ["date", "mm_long", "mm_short", "mm_net"]
    assert len(df) == 0


def test_parse_cot_sorted_ascending():
    rows = [
        {"As_of_Date_In_Form_YYMMDD": "240115", "CFTC_Commodity_Code": "088691",
         "M_Money_Positions_Long_All": 100, "M_Money_Positions_Short_All": 50},
        {"As_of_Date_In_Form_YYMMDD": "240108", "CFTC_Commodity_Code": "088691",
         "M_Money_Positions_Long_All": 90, "M_Money_Positions_Short_All": 40},
    ]
    buf = _make_cot_csv(rows)
    result = parse_cot_upload(buf)
    dates = result["date"].tolist()
    assert dates == sorted(dates), "Rows should be sorted ascending by date"
