
"""КТ-01: проверка результатов инвентаризации.

Запуск из корня mongodb-practice:
    docker compose run --rm python kt01/check.py

Проверяет данные в базе sandbox после запуска inventory.py.
"""

import os
import sys
from pymongo import MongoClient

URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")


def check(condition, success, failure):
    if condition:
        print(f"[OK] {success}")
        return True
    print(f"[FAIL] {failure}")
    return False


def main():
    passed = 0
    failed = 0

    def verify(condition, success, failure):
        nonlocal passed, failed
        if check(condition, success, failure):
            passed += 1
        else:
            failed += 1

    client = MongoClient(URI, serverSelectionTimeoutMS=5000)

    try:
        client.admin.command("ping")
        print("[OK] Подключение к MongoDB")

        sandbox = client["sandbox"]
        warehouse = sandbox["warehouse"]
        stocktake = sandbox["stocktake"]
        log_collection = sandbox["stocktake_log"]

        warehouse_rows = list(warehouse.find({}))
        stocktake_rows = list(stocktake.find({}))

        warehouse_by_sku = {
            row["sku"]: row for row in warehouse_rows if "sku" in row
        }
        stocktake_by_sku = {
            row["sku"]: row for row in stocktake_rows if "sku" in row
        }

        verify(
            len(stocktake_rows) > 0,
            f"Пересчёт загружен: {len(stocktake_rows)} документов",
            "Коллекция sandbox.stocktake пустая",
        )

        verify(
            len(stocktake_by_sku) == len(stocktake_rows),
            "Дубликатов SKU в пересчёте нет",
            "В sandbox.stocktake найдены повторяющиеся SKU",
        )

        missing = sorted(set(stocktake_by_sku) - set(warehouse_by_sku))
        verify(
            not missing,
            "Все артикулы пересчёта найдены в warehouse",
            f"Артикулы отсутствуют в учёте: {missing}",
        )

        mismatches = []
        for sku, stock in stocktake_by_sku.items():
            warehouse_row = warehouse_by_sku.get(sku)
            if warehouse_row is None:
                continue
            if warehouse_row.get("qty_accounted", 0) != stock.get("counted", 0):
                mismatches.append(sku)

        verify(
            not mismatches,
            "Учётные остатки совпадают с фактическими",
            f"Остатки не совпадают по SKU: {sorted(mismatches)}",
        )

        zero_skus = {
            sku for sku, row in stocktake_by_sku.items()
            if row.get("counted", 0) == 0
        }
        wrong_zero = [
            sku for sku in zero_skus
            if sku in warehouse_by_sku
            and warehouse_by_sku[sku].get("available") is not False
        ]
        verify(
            not wrong_zero,
            "Все позиции с нулевым фактом помечены available=false",
            f"Не отмечены как недоступные: {sorted(wrong_zero)}",
        )

        nonzero_skus = {
            sku for sku, row in stocktake_by_sku.items()
            if row.get("counted", 0) > 0
        }
        wrong_nonzero = [
            sku for sku in nonzero_skus
            if sku in warehouse_by_sku
            and warehouse_by_sku[sku].get("available") is False
        ]
        verify(
            not wrong_nonzero,
            "Позиции с ненулевым фактом не помечены недоступными",
            f"Ошибочно помечены недоступными: {sorted(wrong_nonzero)}",
        )

        logs = list(log_collection.find({}))
        required_fields = {
            "date", "positions", "mismatches",
            "shortage_units", "surplus_units",
        }
        valid_log = (
            len(logs) == 1
            and required_fields.issubset(logs[0].keys())
        )
        verify(
            valid_log,
            "В журнале одна запись с датой и итоговыми показателями",
            f"Ожидалась одна корректная запись журнала, найдено: {len(logs)}",
        )

        if logs:
            log_entry = logs[0]
            verify(
                log_entry.get("positions") == len(stocktake_rows),
                "Количество позиций в журнале соответствует пересчёту",
                "Количество позиций в журнале не совпадает с пересчётом",
            )

        print("\n" + "=" * 48)
        print(f"Результат: {passed} проверок пройдено, {failed} ошибок.")
        if failed == 0:
            print("Все проверки пройдены.")
        else:
            print("Есть ошибки. Проверь вывод выше.")
            sys.exit(1)

    finally:
        client.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[FAIL] Ошибка проверки: {exc}")
        sys.exit(1)
