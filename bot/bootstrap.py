"""Bootstrap-режим: создание портфеля из 6 ОФЗ для покрытия 12 месяцев."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import combinations
from typing import Any

from t_tech.invest import Client, InstrumentIdType, OrderDirection, OrderType
from t_tech.invest.utils import quotation_to_decimal

logger = logging.getLogger(__name__)

OFZ_CLASS_CODE = "TQOB"
MIN_YEARS_TO_MATURITY = 7
TARGET_BOND_COUNT = 6
CREATION_BUDGET_RUB = Decimal("6000")
ALL_MONTHS = frozenset(range(1, 13))


@dataclass(frozen=True)
class OfzInfo:
    figi: str
    ticker: str
    name: str
    lot_size: int
    last_price_per_bond: Decimal
    nkd_per_bond: Decimal
    coupon_per_bond: Decimal
    maturity_date: datetime
    coupon_months: frozenset[int]

    @property
    def cost_per_lot_rub(self) -> Decimal:
        return (
            self.last_price_per_bond * Decimal(self.lot_size)
            + self.nkd_per_bond * Decimal(self.lot_size)
        )


@dataclass(frozen=True)
class PortfolioSelection:
    bonds: tuple[OfzInfo, ...]
    covered_months: frozenset[int]
    total_cost: Decimal
    is_full_coverage: bool


def _q2d(q: Any) -> Decimal:
    if q is None:
        return Decimal("0")
    return quotation_to_decimal(q)


def get_class_code(client: Client, figi: str) -> str | None:
    """Возвращает class_code облигации по FIGI."""
    try:
        bond = client.instruments.bond_by(
            id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
            id=figi,
        ).instrument
        return bond.class_code
    except Exception:
        return None


def collect_all_ofz(client: Client, now: datetime | None = None) -> list[OfzInfo]:
    reference_now = now or datetime.now(UTC)
    cutoff = reference_now + timedelta(days=MIN_YEARS_TO_MATURITY * 365)
    
    bonds_resp = client.instruments.bonds(instrument_status=1)
    result: list[OfzInfo] = []

    for bond in bonds_resp.instruments:
        if bond.class_code != OFZ_CLASS_CODE:
            continue
        if bond.maturity_date is None or bond.maturity_date < cutoff:
            continue
        if getattr(bond, "floating_coupon_flag", True):
            continue
            
        lot_size = int(bond.lot or 0)
        if lot_size <= 0:
            continue

        try:
            coupons = client.instruments.get_bond_coupons(
                figi=bond.figi,
                from_=reference_now,
                to=reference_now + timedelta(days=365),
            ).events
        except Exception:
            logger.exception("Failed to fetch coupons for %s", bond.figi)
            continue

        months = {c.coupon_date.month for c in coupons if c.coupon_date}
        if not months:
            continue

        avg_coupon = sum(
            (_q2d(c.pay_one_bond) for c in coupons), Decimal("0")
        ) / Decimal(len(coupons))

        result.append(OfzInfo(
            figi=bond.figi,
            ticker=bond.ticker,
            name=bond.name,
            lot_size=lot_size,
            last_price_per_bond=_q2d(bond.last_price),
            nkd_per_bond=_q2d(bond.aci_value) / Decimal(lot_size),
            coupon_per_bond=avg_coupon,
            maturity_date=bond.maturity_date,
            coupon_months=frozenset(months),
        ))
    return result


def select_portfolio_combination(
    candidates: list[OfzInfo], budget: Decimal
) -> PortfolioSelection | None:
    if len(candidates) < TARGET_BOND_COUNT:
        return None

    best: PortfolioSelection | None = None

    for combo in combinations(candidates, TARGET_BOND_COUNT):
        total_cost = sum(c.cost_per_lot_rub for c in combo)
        if total_cost > budget:
            continue

        covered = frozenset().union(*(c.coupon_months for c in combo))
        is_full = covered == ALL_MONTHS
        selection = PortfolioSelection(
            bonds=combo,
            covered_months=covered,
            total_cost=total_cost,
            is_full_coverage=is_full,
        )

        if best is None:
            best = selection
        elif is_full and not best.is_full_coverage:
            best = selection
        elif is_full == best.is_full_coverage:
            if len(covered) > len(best.covered_months):
                best = selection
            elif len(covered) == len(best.covered_months) and total_cost < best.total_cost:
                best = selection

    return best


def run_bootstrap(client: Client, account_id: str, free_rub: Decimal) -> dict[str, Any]:
    # 1. Сначала проверяем, пуст ли портфель.
    portfolio = client.operations.get_portfolio(account_id=account_id)
    has_ofz = False
    for pos in portfolio.positions:
        if int(pos.quantity.units) > 0 and pos.instrument_type == "bond":
            class_code = get_class_code(client, pos.figi)
            if class_code == OFZ_CLASS_CODE:
                has_ofz = True
                break
    
    if has_ofz:
        return {
            "status": "Портфель уже содержит ОФЗ. Покупка не совершается.",
            "action": "Нет покупок (режим рекомендации)",
        }
        
    # 2. Если портфель пуст, проверяем баланс
    if free_rub < CREATION_BUDGET_RUB:
        return {
            "status": f"Недостаточно средств для создания портфеля. Нужно {CREATION_BUDGET_RUB} руб.",
            "action": "Нет покупок",
        }

    # 3. Ищем бумаги и покупаем
    candidates = collect_all_ofz(client)
    if not candidates:
        return {"status": "Не найдено подходящих ОФЗ.", "action": "Нет покупок"}

    selection = select_portfolio_combination(candidates, free_rub)
    if selection is None:
        return {"status": "Не удалось найти комбинацию из 6 ОФЗ.", "action": "Нет покупок"}

    if not selection.is_full_coverage:
        missing = sorted(ALL_MONTHS - selection.covered_months)
        return {
            "status": f"Покрытие неполное. Нет месяцев: {missing}. Стоимость: {selection.total_cost:.2f}",
            "action": "Нет покупок (рекомендация)",
            "recommended_bonds": [c.ticker for c in selection.bonds],
        }

    purchased = []
    for bond in selection.bonds:
        try:
            resp = client.orders.post_order(
                instrument_id=bond.figi,
                quantity=1,
                account_id=account_id,
                direction=OrderDirection.ORDER_DIRECTION_BUY,
                order_type=OrderType.ORDER_TYPE_MARKET,
                order_id="",
            )
            purchased.append({"ticker": bond.ticker, "order_id": resp.order_id})
        except Exception as exc:
            logger.exception("Ошибка покупки %s", bond.ticker)
            purchased.append({"ticker": bond.ticker, "error": str(exc)})

    return {
        "status": "Портфель создан.",
        "action": f"Куплено {len(purchased)} ОФЗ",
        "purchased": purchased,
        "total_cost": str(selection.total_cost),
        "covered_months": sorted(selection.covered_months),
    }
