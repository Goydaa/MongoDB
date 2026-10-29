# Команды практикума (logs.events)

Оболочка на базе logs (одна команда, остаётся открытой всю работу):
```
docker compose exec mongo mongosh logs
```
Из папки `mongodb-practice`. Перед началом: `docker compose run --rm reset` (1200 событий, индексов нет).

Проверка перед каждым планом:
```js
db.events.countDocuments()     // 1200
db.events.getIndexes()         // сколько индексов сейчас (кроме _id_ лишних быть не должно)
```

## Как снять план (способ А, Compass)
1. Compass → logs → events.
2. Фильтр в строке запроса, сортировка в Options → Sort, затем кнопка **Explain**.
3. Вкладка **Raw Output** → **Copy** → вставить в новый файл `plan-N.json` (сохранить в UTF-8).
4. Открыть https://dfrancour.dev/tools/mongodb-paste-the-plan , вставить JSON, **Analyze Plan**, затем **Generate Plan Share URL** → Copy. Ссылку записать в таблицу отчёта.

## plan-1 · без индекса
Фильтр: `{ service: "payments", level: "error", duration_ms: { $gt: 500 } }`, сортировка: `{ ts: -1 }`.
Ожидаю: 33 / 1200 / 0, шаги COLLSCAN → SORT.

## plan-2 · индекс по ESR
```js
db.events.createIndex({ service: 1, level: 1, ts: -1, duration_ms: 1 })
```
Тот же запрос. Ожидаю: 33 / 33 / 43, шаги IXSCAN → FETCH.

## plan-3a · диапазон впереди
```js
db.events.dropIndex({ service: 1, level: 1, ts: -1, duration_ms: 1 })
db.events.createIndex({ duration_ms: 1, service: 1, level: 1, ts: -1 })
```
Ожидаю: 33 / 33 / 378, SORT есть.

## plan-3b · диапазон перед сортировкой
```js
db.events.dropIndex({ duration_ms: 1, service: 1, level: 1, ts: -1 })
db.events.createIndex({ service: 1, level: 1, duration_ms: 1, ts: -1 })
```
Ожидаю: 33 / 33 / 33, SORT есть.

## plan-4-bez · второй запрос без индекса
```js
db.events.dropIndex({ service: 1, level: 1, duration_ms: 1, ts: -1 })
```
Запрос: фильтр `{ level: "error" }`, сортировка `{ duration_ms: -1 }`, limit 10 (в Compass: Options → Limit).
Ожидаю: 10 / 1200 / 0, COLLSCAN → SORT.

## plan-4 · свой индекс
Индекс подберите сами: разберите запрос по ESR (что тут равенство, что сортировка, есть ли диапазон).
Ожидаю после индекса: 10 / 10 / 10, шаги IXSCAN → FETCH → LIMIT.

Числа «Ожидаю» из страницы практикума. Не совпали, значит остался лишний индекс (см. `getIndexes()`), а не ошибка в цифрах.
