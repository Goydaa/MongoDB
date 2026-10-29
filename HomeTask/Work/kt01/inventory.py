"""КТ-01: инвентаризация склада.

Загрузка пересчёта идемпотентна; изменения выполняются только в sandbox.
Запуск: python inventory.py
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient, UpdateOne

URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
HERE = Path(__file__).resolve().parent
STOCKTAKE_FILE = HERE / "stocktake.json"
client = MongoClient(URI, serverSelectionTimeoutMS=5000)


def main():
    sandbox = client["sandbox"]
    warehouse = sandbox["warehouse"]
    stocktake_collection = sandbox["stocktake"]
    log_collection = sandbox["stocktake_log"]
    run_date = datetime.now(timezone.utc).date().isoformat()

    counted_rows = json.loads(STOCKTAKE_FILE.read_text(encoding="utf-8"))
    counted_by_sku = {row["sku"]: row for row in counted_rows}

    # Повторный запуск обновляет те же документы по sku, не создавая копии.
    stocktake_ops = [
        UpdateOne(
            {"_id": row["sku"]},
            {"$set": {
                "sku": row["sku"],
                "counted": row["counted"],
                "counted_by": row.get("counted_by", ""),
            }},
            upsert=True,
        )
        for row in counted_rows
    ]
    if stocktake_ops:
        stocktake_collection.bulk_write(stocktake_ops, ordered=True)

    warehouse_rows = list(
        warehouse.find(
            {},
            {"_id": 1, "sku": 1, "title": 1, "category": 1,
             "qty_accounted": 1, "shelf": 1, "last_stocktake": 1, "available": 1},
        )
    )
    warehouse_by_sku = {row["sku"]: row for row in warehouse_rows}

    missing_in_warehouse = sorted(set(counted_by_sku) - set(warehouse_by_sku))
    matched, shortage, surplus = [], [], []
    shortages_total = 0
    surplus_total = 0

    for sku, stock in counted_by_sku.items():
        if sku not in warehouse_by_sku:
            continue
        accounted = warehouse_by_sku[sku].get("qty_accounted", 0)
        actual = stock["counted"]
        if accounted == actual:
            matched.append(sku)
        elif accounted > actual:
            shortage.append(sku)
            shortages_total += accounted - actual
        else:
            surplus.append(sku)
            surplus_total += actual - accounted

    mismatch_skus = shortage + surplus
    mismatch_filter = {"sku": {"$in": mismatch_skus}}
    candidates_before_update = warehouse.count_documents(mismatch_filter)
    print(f"Перед обновлением расхождений найдено: {candidates_before_update}")

    # Каждому SKU задаём собственное фактическое количество.
    # last_stocktake выставляется только при расхождении.
    update_ops = []
    for sku in mismatch_skus:
        update_ops.append(
            UpdateOne(
                {"sku": sku},
                {"$set": {
                    "qty_accounted": counted_by_sku[sku]["counted"],
                    "last_stocktake": run_date,
                }},
            )
        )
    changed_count = warehouse.bulk_write(update_ops, ordered=True).modified_count if update_ops else 0

    # Пустые полки отмечаем, а у товаров с ненулевым фактом убираем этот флаг.
    zero_skus = [sku for sku, row in counted_by_sku.items() if row["counted"] == 0]
    zero_filter = {"sku": {"$in": zero_skus}}
    zero_count = warehouse.count_documents(zero_filter)
    print(f"Перед отметкой пустых полок найдено: {zero_count}")
    if zero_skus:
        warehouse.update_many(zero_filter, {"$set": {"available": False}})

    nonzero_skus = [sku for sku, row in counted_by_sku.items() if row["counted"] > 0]
    nonzero_filter = {"sku": {"$in": nonzero_skus}, "available": False}
    nonzero_count = warehouse.count_documents(nonzero_filter)
    print(f"Перед снятием ошибочного флага найдено: {nonzero_count}")
    if nonzero_skus:
        warehouse.update_many(
            {"sku": {"$in": nonzero_skus}},
            {"$unset": {"available": ""}},
        )

    # Журнал за дату создаётся один раз. Повторный запуск не добавит запись.
    log_filter = {"date": run_date}
    log_values = {
        "date": run_date,
        "positions": len(counted_rows),
        "mismatches": len(mismatch_skus),
        "shortage_units": shortages_total,
        "surplus_units": surplus_total,
    }
    log_result = log_collection.update_one(
        log_filter, {"$setOnInsert": log_values}, upsert=True
    )

    print("\nРезультат сверки:")
    print(f"Позиций в учёте: {len(warehouse_rows)}")
    print(f"Позиций в пересчёте: {len(counted_rows)}")
    print(f"Артикулы пересчёта без учёта: {missing_in_warehouse}")
    print(f"Сошлось ({len(matched)}): {', '.join(sorted(matched))}")
    print(f"Недостача ({len(shortage)}): {', '.join(sorted(shortage))}")
    print(f"Излишек ({len(surplus)}): {', '.join(sorted(surplus))}")
    print(f"Суммарная недостача, шт.: {shortages_total}")
    print(f"Суммарный излишек, шт.: {surplus_total}")
    print(f"Документов учёта изменено: {changed_count}")
    print(f"Журнал: дата={run_date}, добавлена новая запись={log_result.upserted_id is not None}")

    print("\nПустые полки:")
    for row in warehouse.find(
        {"sku": {"$in": zero_skus}},
        {"_id": 0, "sku": 1, "title": 1, "shelf": 1},
    ).sort("sku", 1):
        print(f"  {row.get('sku')} | {row.get('title')} | {row.get('shelf')}")

    # Полезные значения для заполнения inventory.md по фактическим данным.
    print("\nПроверочные запросы для отчёта:")
    print("warehouse.count_documents({}) =", warehouse.count_documents({}))
    print("stocktake.count_documents({}) =", stocktake_collection.count_documents({}))
    print("warehouse.count_documents({'last_stocktake': {'$exists': True}}) =",
          warehouse.count_documents({"last_stocktake": {"$exists": True}}))
    print("stocktake_log.count_documents({}) =", log_collection.count_documents({}))


if __name__ == "__main__":
    try:
        main()
    finally:
        client.close()
