"""
Проверка практической работы MongoDB Explain.
Запуск: python check.py
Скрипт ничего не удаляет и не меняет в базе.
"""
import sys

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
except ImportError:
    print("[FAIL] Не установлен pymongo.")
    print("Установи: python -m pip install pymongo")
    sys.exit(1)

MONGO_URI = "mongodb://localhost:27017"
DATABASE_NAME = "logs"
COLLECTION_NAME = "events"
EXPECTED_DOCUMENTS = 1200


def report(name, ok, detail=""):
    status = "OK" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def main():
    checks = []
    client = None
    print("=" * 58)
    print("Проверка практической работы MongoDB Explain")
    print("=" * 58)
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        checks.append(report("Подключение к MongoDB", True, MONGO_URI))

        db = client[DATABASE_NAME]
        names = db.list_collection_names()
        exists = COLLECTION_NAME in names
        checks.append(report(
            f"Коллекция {DATABASE_NAME}.{COLLECTION_NAME}",
            exists, "найдена" if exists else "не найдена"
        ))
        if not exists:
            print("\nПроверки остановлены: коллекция не найдена.")
            sys.exit(1)

        events = db[COLLECTION_NAME]
        count = events.count_documents({})
        checks.append(report(
            "Количество документов", count == EXPECTED_DOCUMENTS,
            f"найдено {count}, ожидалось {EXPECTED_DOCUMENTS}"
        ))

        query1 = {
            "service": "payments",
            "level": "error",
            "duration_ms": {"$gt": 500},
        }
        count1 = events.count_documents(query1)
        checks.append(report(
            "Запрос для планов 1–3", count1 == 33,
            f"найдено {count1}, ожидалось 33"
        ))

        result4 = list(
            events.find({"level": "error"}, {"_id": 1})
            .sort("duration_ms", -1).limit(10)
        )
        checks.append(report(
            "Запрос для плана 4", len(result4) == 10,
            f"получено {len(result4)} документов"
        ))

        indexes = list(events.list_indexes())
        index_names = [idx["name"] for idx in indexes]
        print("\nИндексы коллекции:")
        for name in index_names:
            print(f"  - {name}")
        checks.append(report("Индекс _id_ присутствует", "_id_" in index_names))

        print("\n" + "=" * 58)
        passed, total = sum(checks), len(checks)
        print(f"Результат: {passed}/{total} проверок пройдено.")
        print("Все базовые проверки пройдены." if passed == total
              else "Есть проверки, требующие внимания. Сверь базу и данные.")
        print("=" * 58)
        sys.exit(0 if passed == total else 1)

    except PyMongoError as exc:
        report("Ошибка подключения или запроса", False, str(exc))
        print("Убедись, что MongoDB запущена и порт 27017 доступен.")
        sys.exit(1)
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
