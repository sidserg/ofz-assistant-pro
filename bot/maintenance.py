"""Модуль докупки ОФЗ (Maintenance)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from datetime import UTC, datetime, timedelta

from t_tech.invest import Client, InstrumentIdType, OrderDirection, OrderType
from t_tech.invest.utils import quotation_to_decimal

logger = logging.getLogger(__name__)

OFZ_CLASS_CODE = "TQOB"
MIN_THRESHOLD_RUB = Decimal("600")
COUPON_NKD_LIMIT_RATIO = Decimal("0.5")


@dataclass(frozen=True)
class OfzCandidate:
    figi: str
    ticker: str
    name: str
    lot_size: int
    last_price_per_bond: Decimal
    nkd_per_bond: Decimal
    coupon_per_bond: Decimal

    @property
    def cost_per_lot_rub(self) -> Decimal:
        return (
            self.last_price_per_bond + self.nkd_per_bond
        ) * Decimal(self.lot_size)


def _q2d(q) -> Decimal:
    if q is None:
        return Decimal("0")
    return quotation_to_decimal(q)


def collect_ofz_from_portfolio(client: Client, account_id: str) -> list[OfzCandidate]:
    portfolio = client.operations.get_portfolio(account_id=account_id)
    result: list[OfzCandidate] = []

    for pos in portfolio.positions:
        if pos.instrument_type != "bond":
            continue
        if int(pos.quantity.units) <= 0:
            continue

        try:
            bond = client.instruments.bond_by(
                id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
                id=pos.figi,
            ).instrument
            if bond.class_code != OFZ_CLASS_CODE:
                continue
        except Exception:
            logger.exception("Failed to fetch bond_by for %s", pos.figi)
            continue

        lot_size = int(bond.lot or 0)
        if lot_size <= 0:
            continue

        # Получаем купон из графика выплат
        try:
            coupons = client.instruments.get_bond_coupons(
                figi=pos.figi,
                from_=datetime.now(UTC),
                to=datetime.now(UTC) + timedelta(days=30),
            ).events
            if not coupons:
                continue
            coupon_per_bond = _q2d(coupons[0].pay_one_bond)
        except Exception:
            logger.exception("Failed to fetch coupons for %s", pos.figi)
            continue

        # Получаем актуальную цену
        try:
            last_price = client.market_data.get_last_prices(figi=[pos.figi]).last_prices[0].price
            last_price_per_bond = _q2d(last_price)
        except Exception:
            logger.exception("Failed to fetch price for %s", pos.figi)
            continue

        # current_nkd в портфеле — это НКД на одну бумагу
        nkd_per_bond = _q2d(pos.current_nkd)

        result.append(OfzCandidate(
            figi=pos.figi,
            ticker=bond.ticker,
            name=bond.name,
            lot_size=lot_size,
            last_price_per_bond=last_price_per_bond,
            nkd_per_bond=nkd_per_bond,
            coupon_per_bond=coupon_per_bond,
        ))

    return result


def select_bond_to_buy(candidates: list[OfzCandidate]) -> OfzCandidate | None:
    eligible = [
        c for c in candidates
        if c.coupon_per_bond > Decimal("0")
        and c.nkd_per_bond / c.coupon_per_bond <= COUPON_NKD_LIMIT_RATIO
    ]
    if not eligible:
        return None
    eligible.sort(key=lambda c: c.nkd_per_bond)
    return eligible[0]


def calculate_buy_quantity(bond: OfzCandidate, free_rub: Decimal) -> int:
    cost = bond.cost_per_lot_rub
    if cost <= Decimal("0"):
        return 0
    return int((free_rub / cost).to_integral_value(rounding=ROUND_DOWN))


def run_maintenance(client: Client, account_id: str, free_rub: Decimal) -> dict:
    if free_rub < MIN_THRESHOLD_RUB:
        return {
            "status": f"Баланс меньше порога ({MIN_THRESHOLD_RUB}).",
            "action": "Нет покупок"
        }

    candidates = collect_ofz_from_portfolio(client, account_id)
    if not candidates:
        return {"status": "В портфеле нет ОФЗ.", "action": "Нет покупок"}

    bond = select_bond_to_buy(candidates)
    if bond is None:
        return {
            "status": "Все ОФЗ отсеяны (НКД > 50% купона).",
            "action": "Нет покупок"
        }

    lots = calculate_buy_quantity(bond, free_rub)
    if lots <= 0:
        return {
            "status": f"Не хватает на 1 лот {bond.ticker} (цена {bond.cost_per_lot_rub:.2f}).",
            "action": "Нет покупок",
            "selected_bond": bond.ticker,
        }

    try:
        response = client.orders.post_order(
            instrument_id=bond.figi,
            quantity=lots,
            account_id=account_id,
            direction=OrderDirection.ORDER_DIRECTION_BUY,
            order_type=OrderType.ORDER_TYPE_MARKET,
            order_id="",
        )
        logger.info("Bought %d lots of %s", lots, bond.ticker)
        return {
            "status": "Покупка совершена.",
            "action": f"Куплено {lots} лотов {bond.ticker}",
            "selected_bond": bond.ticker,
            "qty_lots": lots,
            "nkd_per_bond": str(bond.nkd_per_bond),
            "coupon_per_bond": str(bond.coupon_per_bond),
            "cost_per_lot": str(bond.cost_per_lot_rub),
            "order_id": response.order_id,
        }
    except Exception as exc:
        logger.exception("post_order failed")
        return {
            "status": f"Ошибка заявки: {exc}",
            "action": "Нет покупок",
            "selected_bond": bond.ticker,
        }
