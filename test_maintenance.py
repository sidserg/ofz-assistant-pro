"""Тесты для модуля maintenance."""
import pytest
from decimal import Decimal
from bot.maintenance import (
    OfzCandidate,
    select_bond_to_buy,
    calculate_buy_quantity,
    COUPON_NKD_LIMIT_RATIO,
)


def _make_candidate(
    ticker: str,
    nkd: str,
    coupon: str,
    price: str = "800",
    lot: int = 1,
) -> OfzCandidate:
    return OfzCandidate(
        figi=f"FIGI_{ticker}",
        ticker=ticker,
        name=ticker,
        lot_size=lot,
        last_price_per_bond=Decimal(price),
        nkd_per_bond=Decimal(nkd),
        coupon_per_bond=Decimal(coupon),
    )


def test_select_filters_out_nkd_above_limit():
    # НКД 54.70, купон 61.08 -> отношение ~0.895 > 0.5, должна отсеяться
    bad = _make_candidate("BAD", nkd="54.70", coupon="61.08")
    good = _make_candidate("GOOD", nkd="10.00", coupon="61.08")
    result = select_bond_to_buy([bad, good])
    assert result is not None
    assert result.ticker == "GOOD"


def test_select_returns_none_when_all_filtered():
    bad = _make_candidate("BAD", nkd="54.70", coupon="61.08")
    assert select_bond_to_buy([bad]) is None


def test_select_picks_min_nkd_among_eligible():
    a = _make_candidate("A", nkd="20.00", coupon="61.08")
    b = _make_candidate("B", nkd="10.00", coupon="61.08")
    result = select_bond_to_buy([a, b])
    assert result.ticker == "B"


def test_select_boundary_exact_50_percent_passes():
    # ровно 50% должно проходить (условие <=)
    edge = _make_candidate("EDGE", nkd="30.54", coupon="61.08")
    result = select_bond_to_buy([edge])
    assert result is not None
    assert result.ticker == "EDGE"


def test_calculate_buy_quantity_includes_nkd():
    # цена 800 + НКД 50 = 850 за бумагу, лот 1 -> 850 за лот
    bond = _make_candidate("X", nkd="50", coupon="61.08", price="800", lot=1)
    qty = calculate_buy_quantity(bond, Decimal("1700"))
    assert qty == 2


def test_calculate_buy_quantity_zero_on_insufficient_funds():
    bond = _make_candidate("X", nkd="50", coupon="61.08", price="800", lot=1)
    assert calculate_buy_quantity(bond, Decimal("800")) == 0
