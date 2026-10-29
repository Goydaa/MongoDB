"""ПР-01: каталог товаров и приёмка поставки.

Запускать после загрузки учебных данных. Изменения выполняются только в
sandbox.products; shop.products используется исключительно для чтения.
"""
import os
from pymongo import MongoClient
from pymongo.errors import BulkWriteError

URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(URI, serverSelectionTimeoutMS=5000)
shop_products = client["shop"]["products"]
sandbox_products = client["sandbox"]["products"]

ARRIVALS = {
    "SKU-NB-001": 5,
    "SKU-PH-006": 12,
    "SKU-PR-010": 3,
}
NEW_PRODUCTS = [
    {
        "_id": "p-101",
        "sku": "SKU-AC-101",
        "title": "Подставка для ноутбука",
        "brand": "OEM",
        "category": "аксессуары",
        "price": 2490,
        "reviews": 0,
    },
    {
        "_id": "p-102",
        "sku": "SKU-AC-102",
        "title": "Чехол для планшета",
        "brand": "OEM",
        "category": "аксессуары",
        "price": 1890,
        "reviews": 0,
    },
]


def catalog_page(category=None, page=1, per_page=5, sort_field="price", desc=True):
    """Вернуть (страницу товаров, общее количество по фильтру)."""
    if page < 1 or per_page < 1:
        raise ValueError("page и per_page должны быть положительными числами")

    query = {"category": category} if category else {}
    total = shop_products.count_documents(query)
    direction = -1 if desc else 1
    projection = {"_id": 0, "sku": 1, "title": 1, "price": 1, "rating": 1}
    cursor = (
        shop_products.find(query, projection)
        .sort([(sort_field, direction), ("sku", 1)])
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    return list(cursor), total


def print_catalog_examples():
    print("ЗАДАЧА 1 — каталог")
    for category, page, size, label in [
        ("ноутбуки", 1, 3, "Ноутбуки, страница 1"),
        ("ноутбуки", 2, 3, "Ноутбуки, страница 2"),
        (None, 1, 5, "Весь каталог: первые пять по цене"),
        ("ноутбуки", 99, 3, "Пустая страница"),
    ]:
        items, total = catalog_page(category, page, size)
        print(f"\n{label}; найдено всего: {total}")
        for item in items:
            print(item)
        if not items:
            print("(на этой странице товаров нет)")


def receive_delivery():
    print("\nЗАДАЧА 2 — приёмка поставки")
    report = {}

    # $inc изменяет остаток на сервере, не перезаписывая значение,
    # которое могло измениться после чтения клиентом.
    changed_stock = 0
    for sku, quantity in ARRIVALS.items():
        result = sandbox_products.update_one(
            {"sku": sku}, {"$inc": {"qty_total": quantity}}
        )
        changed_stock += result.modified_count
        print(f"Остаток {sku}: найдено {result.matched_count}, изменено {result.modified_count}")
    report["остатки обновлены"] = changed_stock

    # Фиксированные _id не позволяют создать дубли при повторной вставке.
    try:
        inserted = sandbox_products.insert_many(NEW_PRODUCTS, ordered=False)
        report["новых позиций добавлено"] = len(inserted.inserted_ids)
    except BulkWriteError as exc:
        errors = exc.details.get("writeErrors", [])
        duplicates = sum(1 for error in errors if error.get("code") == 11000)
        other_errors = [error for error in errors if error.get("code") != 11000]
        if other_errors:
            raise
        report["новых позиций добавлено"] = len(NEW_PRODUCTS) - duplicates
        print(f"Новинки, уже существовавшие в базе: {duplicates}")

    discontinued_filter = {"sku": "SKU-CP-018"}
    before_delete = sandbox_products.count_documents(discontinued_filter)
    print(f"Перед удалением SKU-CP-018 найдено: {before_delete}")
    for item in sandbox_products.find(
        discontinued_filter, {"_id": 1, "sku": 1, "title": 1, "price": 1}
    ):
        print("К удалению:", item)
    deleted = sandbox_products.delete_many(discontinued_filter)
    report["удалено позиций"] = deleted.deleted_count

    accessories_filter = {"category": "аксессуары"}
    accessories_count = sandbox_products.count_documents(accessories_filter)
    delivery_update = sandbox_products.update_many(
        accessories_filter, {"$set": {"free_shipping": True}}
    )
    report["аксессуаров найдено"] = accessories_count
    report["документов изменено для бесплатной доставки"] = delivery_update.modified_count
    report["позиций в sandbox после приёмки"] = sandbox_products.count_documents({})

    print("\nИтог приёмки:")
    for label, value in report.items():
        print(f"  {label}: {value}")


if __name__ == "__main__":
    try:
        print_catalog_examples()
        receive_delivery()
    finally:
        client.close()
