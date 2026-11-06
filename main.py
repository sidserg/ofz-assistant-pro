import os
import json
from datetime import datetime
from decimal import Decimal

from t_tech.invest import Client, RequestError, InstrumentIdType
from t_tech.invest.utils import quotation_to_decimal

from bot.maintenance import run_maintenance
from bot.bootstrap import run_bootstrap


def load_config():
    if not os.path.exists("config.json"):
        return {"create_portfolio": False}
    with open("config.json", "r") as f:
        return json.load(f)


def q2f(q) -> float:
    return float(quotation_to_decimal(q))


def get_free_rub(client, account_id):
    try:
        limits = client.operations.get_withdraw_limits(account_id=account_id)
        for money in limits.money:
            if money.currency == "rub":
                return q2f(money)
        return 0.0
    except RequestError:
        return 0.0


def get_portfolio_assets(client, account_id):
    assets = []
    try:
        portfolio = client.operations.get_portfolio(account_id=account_id)
        for pos in portfolio.positions:
            item = {
                "ticker": "UNKNOWN",
                "type": pos.instrument_type,
                "quantity": q2f(pos.quantity),
                "price": q2f(pos.current_price),
            }
            try:
                if pos.instrument_type == "bond":
                    bond = client.instruments.bond_by(
                        id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI, id=pos.figi
                    ).instrument
                    item["ticker"] = bond.ticker
                    item["name"] = bond.name
                    item["price"] = q2f(pos.current_price) + (
                        q2f(pos.current_nkd) if pos.current_nkd else 0
                    )
                elif pos.instrument_type == "share":
                    share = client.instruments.share_by(
                        id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI, id=pos.figi
                    ).instrument
                    item["ticker"] = share.ticker
                    item["name"] = share.name
                elif pos.instrument_type == "etf":
                    etf = client.instruments.etf_by(
                        id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI, id=pos.figi
                    ).instrument
                    item["ticker"] = etf.ticker
                    item["name"] = etf.name
                elif pos.instrument_type == "currency":
                    item["ticker"] = pos.figi
                    item["name"] = "Валюта"
            except Exception:
                pass
            assets.append(item)
    except RequestError as e:
        print(f"Ошибка портфеля: {e}")
    return assets


def generate_report_file(token_name, account_id, free_rub, status_text, assets, extra=None):
    os.makedirs("reports", exist_ok=True)
    now = datetime.now()
    filename = f"reports/{now.strftime('%Y-%m-%d_%H-%M-%S')}_{token_name.replace(' ', '_')}.json"

    report_data = {
        "date": now.strftime("%Y-%m-%d %H:%M:%S"),
        "portfolio": token_name,
        "account_id": account_id,
        "free_rub": round(free_rub, 2),
        "status": status_text,
        "action": "Нет покупок",
        "assets": assets,
    }
    if extra:
        report_data.update(extra)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print(f"Отчет сохранен в {filename}")


def process_account(token, token_name):
    if not token:
        return

    config = load_config()
    create_flag = config.get("create_portfolio", False)

    try:
        with Client(token) as client:
            accounts = client.users.get_accounts().accounts
            if not accounts:
                return
            account_id = accounts[0].id

            free_rub = get_free_rub(client, account_id)
            assets = get_portfolio_assets(client, account_id)

            if create_flag:
                result = run_bootstrap(client, account_id, Decimal(str(free_rub)))
            else:
                result = run_maintenance(client, account_id, Decimal(str(free_rub)))

            status = result["status"]
            extra = {k: v for k, v in result.items() if k != "status"}

            generate_report_file(token_name, account_id, free_rub, status, assets, extra)
            print(f"{token_name}: {status}")
            print(f"Действие: {result.get('action', 'Нет покупок')}")

    except Exception as e:
        print(f"Критическая ошибка [{token_name}]: {e}")
        generate_report_file(token_name, "UNKNOWN", 0.0, f"Ошибка: {e}", [])


from generate_html import generate_html_report

def main():
    token_1 = os.environ.get("TINKOFF_TOKEN")
    token_2 = os.environ.get("TINKOFF_TOKEN_2")
    process_account(token_1, "Портфель 1")
    if token_2:
        process_account(token_2, "Портфель 2")

    # Генерируем статический HTML после обработки всех портфелей
    generate_html_report()


if __name__ == "__main__":
    main()
