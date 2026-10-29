# Практическая работа: Explain и индексы в MongoDB

## 1. Цель работы

Изучить механизм `explain()` в MongoDB, научиться анализировать планы выполнения запросов и исследовать влияние индексов на производительность поиска и сортировки документов.

В ходе работы необходимо:
- выполнить запросы без дополнительных индексов;
- изучить показатели выполнения запросов;
- создать составные индексы с различным порядком полей;
- сравнить количество просмотренных документов и ключей индекса;
- проверить, как порядок полей в индексе влияет на фильтрацию и сортировку;
- сохранить планы выполнения в JSON и сформулировать выводы.

## 2. Используемое окружение

- **СУБД:** MongoDB
- **Инструмент:** MongoDB Compass и встроенная Mongosh
- **Адрес подключения:** `localhost:27017`
- **База данных:** `logs`
- **Коллекция:** `events`
- **Количество документов:** 1200

Для анализа использовался метод `explain("executionStats")`, который позволяет получить фактическую статистику выполнения запроса.

Основные показатели:

- `nReturned` — количество документов, возвращённых запросом;
- `totalDocsExamined` — количество просмотренных документов;
- `totalKeysExamined` — количество просмотренных ключей индекса;
- `winningPlan` — выбранный MongoDB план выполнения запроса.

## 3. Ход работы

### 3.1. План 1 — запрос без дополнительного индекса

Был выполнен запрос с фильтрацией по сервису, уровню ошибки и длительности операции, а также сортировкой по времени:

```javascript
db.events.find({
  service: "payments",
  level: "error",
  duration_ms: { $gt: 500 }
}).sort({
  ts: -1
}).explain("executionStats")
```

На этом этапе дополнительный индекс для запроса не создавался.

Ожидаемый результат:
- возвращено документов: 33;
- просмотрено документов: 1200;
- просмотрено ключей индекса: 0;
- основные этапы: `COLLSCAN` и `SORT`.

`COLLSCAN` означает последовательное сканирование коллекции. MongoDB проверяет документы коллекции, чтобы найти подходящие условиям запроса. Для сортировки найденных результатов используется этап `SORT`.

Результат показывает, что без подходящего индекса MongoDB приходится просматривать всю коллекцию.

План выполнения сохранён в `plan-1.json`.


### 3.2. План 2 — индекс с приоритетом фильтрации и сортировки

Был создан составной индекс:

```javascript
db.events.createIndex({
  service: 1,
  level: 1,
  ts: -1,
  duration_ms: 1
})
```

Затем был повторно выполнен запрос из первого эксперимента с использованием `explain("executionStats")`.

Ожидаемый результат:
- возвращено документов: 33;
- просмотрено документов: 33;
- просмотрено ключей индекса: 43;
- основные этапы: `IXSCAN` и `FETCH`.

`IXSCAN` означает сканирование индекса. MongoDB использует индекс для поиска подходящих записей, после чего `FETCH` получает соответствующие документы из коллекции.

По сравнению с запросом без индекса количество просмотренных документов уменьшается с 1200 до 33. Это показывает, что правильно подобранный индекс может существенно сократить объём чтения документов.

План выполнения сохранён в `plan-2.json`.


### 3.3. План 3a — индекс с полем диапазона на первом месте

Для следующего эксперимента был создан индекс:

```javascript
db.events.createIndex({
  duration_ms: 1,
  service: 1,
  level: 1,
  ts: -1
})
```

В этом индексе поле `duration_ms`, используемое для условия диапазона `$gt`, расположено первым.

Ожидаемый результат:
- возвращено документов: 33;
- просмотрено документов: 33;
- просмотрено ключей индекса: 378;
- в плане присутствует этап `SORT`.

Количество просмотренных ключей увеличивается по сравнению с предыдущим индексом. Кроме того, MongoDB не может полностью использовать этот порядок полей индекса для выполнения сортировки по `ts`, поэтому требуется отдельная сортировка.

Эксперимент показывает, что индекс может помогать находить документы, но при этом не обеспечивать эффективную сортировку.

План выполнения сохранён в `plan-3a.json`.


### 3.4. План 3b — поля равенства перед полем диапазона

Индекс из предыдущего эксперимента был заменён индексом:

```javascript
db.events.createIndex({
  service: 1,
  level: 1,
  duration_ms: 1,
  ts: -1
})
```

В данном варианте поля `service` и `level`, используемые для точного совпадения, расположены перед полем диапазона `duration_ms`.

Ожидаемый результат:
- возвращено документов: 33;
- просмотрено документов: 33;
- просмотрено ключей индекса: 33;
- в плане присутствует этап `SORT`.

По сравнению с планом 3a количество просмотренных ключей уменьшается с 378 до 33. Однако сортировка по `ts` всё ещё требует отдельного этапа, поскольку перед полем сортировки в индексе находится поле диапазона.

Этот эксперимент демонстрирует, что порядок полей в составном индексе влияет как на эффективность поиска, так и на возможность использовать индекс для сортировки.

План выполнения сохранён в `plan-3b.json`.


### 3.5. План 4 — сортировка и ограничение количества результатов без индекса

Был выполнен запрос, который выбирает документы с уровнем `error`, сортирует их по длительности операции в порядке убывания и возвращает не более десяти документов:

```javascript
db.events.find({
  level: "error"
}).sort({
  duration_ms: -1
}).limit(10).explain("executionStats")
```

Для первого варианта дополнительный индекс не использовался.

Ожидаемый результат:
- возвращено документов: 10;
- просмотрено документов: 1200;
- просмотрено ключей индекса: 0;
- основные этапы: `COLLSCAN`, `SORT` и ограничение результата `LIMIT` (точное представление этапов зависит от версии MongoDB и выбранного плана).

Несмотря на ограничение в десять результатов, MongoDB необходимо проверить документы коллекции и определить, какие из них подходят под фильтр и должны оказаться в начале отсортированного результата.

План выполнения сохранён в `plan-4-bez.json`.


### 3.6. План 4 — запрос с индексом

Для оптимизации предыдущего запроса был создан индекс:

```javascript
db.events.createIndex({
  level: 1,
  duration_ms: -1
})
```

Затем запрос был выполнен повторно:

```javascript
db.events.find({
  level: "error"
}).sort({
  duration_ms: -1
}).limit(10).explain("executionStats")
```

Ожидаемый результат:
- возвращено документов: 10;
- просмотрено документов: 10;
- просмотрено ключей индекса: 10;
- основные этапы: `IXSCAN`, `FETCH` и ограничение результата `LIMIT` (точное расположение этапов зависит от версии MongoDB).

Индекс позволяет сначала отобрать записи по `level`, а затем получать их в порядке убывания `duration_ms`. Поэтому отдельная сортировка может не понадобиться.

По сравнению с вариантом без индекса количество просмотренных документов уменьшается с 1200 до 10.

План выполнения сохранён в `plan-4.json`.

## 4. Сводная таблица результатов

Ниже приведены ожидаемые значения для сравнения. Перед сдачей необходимо сверить их с фактическими полями `executionStats` в каждом JSON-файле.

| План | Индекс | Возвращено | Документов просмотрено | Ключей просмотрено | Основные этапы плана | Ссылка на разбор |
|---|---|---:|---:|---:|---|---|
| 1 | Без дополнительного индекса | 33 | 1200 | 0 | `COLLSCAN → SORT` | [Plan 1](https://dfrancour.dev/tools/mongodb-paste-the-plan?utm_source=chatgpt.com#v1:zVVtb-M2DP4vxH30irhp3vytTZOtuGbp6m6Hw2EYWIl2tciST6JT54L890Fy07T30h5uwLBPtkk-pPg8pLUFamuNyvxBzitrIIMUEvjYkNtcaTSGHGRbMFiRr1EQZKBt6Y9oTYY9JKCMpHauNJPLiSErUHtKoEbnSf4W0gT8GzQSsg9b0LQmHS30ETIg56yD3S7Zgie3VqHA3lfjpopFols2DllZ81flY0jJkA16vd3uz93DcX9BfwcZTM_Sk8FsfA4J1BrNFMUdvaXNc4-tWVXqU8x4oypaKK2Vh6yXQIXtReiJ5NLlVjchxF9TSCMf2zsEnRr5UlQu0PgbO2trbSV9HnCvjFGmDESHpjxjGRjOl9c3kIC3jq-QmVz0sofsp3SXQEXVpaoUQ5b2TsaD0bDXS4A3dYB6VdWaoi51w3mX8JB5ury8zKenv0ICRdTsPxBHKkeCu9kqrLtHJwMKHP1NgkmG7j1kH0IstSQilzkjx1wHSyMEeQ8Zu4YSMNfEjTOBzH7_CfAzNdky6re08bMWKxXD99ZzK55Y0-PA4tP6JfmviPJ63ZlnVSFTrHRv3cqH7P1BAijXaMQeaohkQMXaaff9XpHujuhxTYGE4A5cebbuiUH52XIe3_7VlHREIGOuPlFuHYfDTdJxmkDjSZ4rv3ocVl8rrTtW4yvJCGTrsKSAj67_z9z9qFJBi28qlQ5HP6zU1xYhAfnFGO7CdghbVZGfLRQqPOHxl3tg8JGeAy_Jns0HGpNvk9TNzrOh8StVx6Z0Nzrd_zAylkM27PXCEL2Rtw_XAAQIuTW5C1PYkOnOeoYMhgXhMQrEyShcJ3WsczzqpaME1o83zeiod3QygARKxYf7BwfH_bRPaR9vBwMxuZWyGIl-UUxSibfH42GB_XE6mgwPxa_QYUVMLjaoTNgF1PHymaMgPmuKglwY0bMNh61-shFfRi-wXTZcN3xuxcuYS2tXTR2H_SKYKpIKmc6taIIYC2xfxu8Dc9s4QT8729QLbBdUWbd55aQLbM-0FStlyrC2HeZ3j-VrLV45e6duFe_RC3IlLc3CmtLmDxv8vM6plDc2J_7ePnLid8pIez8PK-K_t6N50DAs4dQadlZ3SyJoqtF7JWamVIaC5nYFWbr7Bw) |
| 2 | `{ service: 1, level: 1, ts: -1, duration_ms: 1 }` | 33 | 33 | 43 | `IXSCAN → FETCH` | [Plan 2](https://dfrancour.dev/tools/mongodb-paste-the-plan?utm_source=chatgpt.com#v1:7VZLc9s2EP4rnp0cekA8pGVZNm_Wq_G4ipXQ6WMcj2ZFLGVEIEADoEzFo__eAain29o5tjM9kVzs69v9sMtnoLqUKNSvZKzQChKIgcFjRWY5lqgUGUieQWFBtsSMIAGpZ_aYFqScBQZCcaqHQjoyKTlIcpSWGJRoLPFP3o23f4eKQ3L3DJIWJIOEHiEBMkYbWK3YM1gyC-EDbM5KXBYhSDjmlUEntJoUNqjMHCTtKFqt7lfrdD-gfYAEet34tD047wODUqLqYfZA17SEBPrDbhzHgy4w0KUThfgePN6KgkZCSmEhiRgUWF95TMRvTKpl5VXsZ_Ju-BbeTulS8de00gyVvdWDupSa00uFJ6GUUDNfaA_KOpz5Cg8Ht70PobZl5dJGuDu9-j3tXX4EBnNajtE5Mo3xpn4x21Q5ZuAsJO9jdli-eLXu20csvMe16SSeBMNJPHF28j6e7BlNPCuEHVXSiVDNDcS1YIzuwR6kcXe_zcO_-kT88yCRO988Yb8o8VjR1qewaaDPnmCMxgmUO4nPfkvZEwZcGMpcQ-Bcmyc0fEPOrq4Uf5Eb3H3d8usrsKP9r3vYy9wrBpI2WuvXoBIQwd0I62tasqORUNe0DCeHGOGndhSxI6Hy4-ge7lerFQND3yhzxH3nN3WgmrLAo9ShC_nuJFWWkbWQOFMRA_WZXGWUJ1KrtWf4gslOO5TXtLSDGgsR1E9ba3FfZ3viAy-BcPbv-Ph23IF1okBHIf6TNnPbxES-QJVtDBUR9zaQXDQffwiSPNhYXJDH33gwZJ02ewJhBzfDQGz-FwAoDSH3Y-Bm-q3Rfv3-_Jvg_H-X_5N3OTTuxf2yRJ4nceSNS3tL1lHDBv_ZN7osw3cYBJkuirAbnyEX_gnbzZqHpXqAdbcTt6jWK5T984JkYLVxXtYQyAvmogwZSVEIt1l7gfcpJGdRFEUM3vHpetuDNyGzIHOlcu09PWjrIIGznPAEM8SLjudUGeKcdKK4w2Cx_aHoHEfHp21gMBNu95uB7ZNW3KK4hdN2O7uYcp53slaeX8QcpyfnZzm2zuPOxdku-BgNFuTIBIBC-duCMvxjDDEj163ynEwqvlN36Si04PS83TmLwih4qT3C-qZyZeX6Onvd5het51UZ5siVFxXEBTrq66zyzRhh_br9RjHVlcnoZ6OrcoT1iAptlm9kOsK6K3U2F2qWauMamy8WZ29BHBv9IKbCbaxHZGZ0o0ZazXS6Ho6HcS45v9UpuR_FkZL7TSiun4Z-2tkfRTT0PfSjtKeVM1o2dzyjnkRrRTZQM6HI91zP_XD7Ew) |
| 3a | `{ duration_ms: 1, service: 1, level: 1, ts: -1 }` | 33 | 33 | 378 | `IXSCAN → FETCH → SORT` | [Plan 3a](https://dfrancour.dev/tools/mongodb-paste-the-plan?utm_source=chatgpt.com#v1:7VZLUxs5EP4rVFcOe1CoGYxtmBt-bSjimGXIPopQrvaoxyjWSIOkATuU__uWNH4BAVLZy27Vnjxq9ePr1tftfgCalxKF-p2MFVpBAjEwuK3ILM4lKkUGkgdQWJAtMSNIQOqp3ac7Us4CA6E4zQdCOjIpOUhylJYYlGgs8d-8G2__DhWH5OoBJN2RDBK6hQTIGG1guWQPYMncCR9gfVfioghBwjWvDDqh1biwQWXqIGlG0XJ5vVzB_YD2BhLoduLDZv-oBwxKiaqL2Q2d0QIS6A06cRz3O8BAl04U4lvweCkKGgophYUkYlDg_NTnRHxkUi0rr2IvyLvhm_S2SieKv6aVZqjspe7PS6k5PVW4F0oJNfWF9klZh1Nf4UH_svsh1LasXFoLt7fp6OISGFht3Dk6RybYOgvJ-3jJoKDioyiEgySODo-a7VYUMXCL0ptyyrGS7kXXp3-m3ZNPwGBGix3fj2ofs-1TxWz9oDHbIgiU-IRFiLg1HcfjleE4HgezcTx2dvzeE07YYSWdCA-1rt5KcI7uxj6DcXW9g8MfVkD8pwv3Hon9rMRtRRufwqaBmTuCczROoNxKPPpNNxww4MJQ5ureyLW5R8PXvO_oSvHvYINfmlHE9oTK96NreIQUrr5smP0F2N7uKaiu8_CKoT1qrdVnUAn5wdUQ52e0YHtDoc5ocQ3Xy-VyycDQV8occc-qdSFoTlngaOrQBcBbSZVlZC0kzlTEQF2Qq4zyJG00dgyfdInTDuUZLWx_joWo1dtHK3lPZ7vyxuP4U7LfI_vbgfvWiQIdBQD32swsJIdxgwHyO1TZ2lIRcW_kER3Xx78ESR7MLN6Rr0HtxJB12uwIhO2PBoHN_FkOKA0h92NmNPlaa7_Wn_-yfP7ZuKifFR2m4hul2rgALm4dMags8Z6ws00D2VJIWbMkfBIPhk4bnJK3f6V2mwH0c9ULBXqxeofNn67e__PwPzkPw8M9HVGWKHDlsMWAV6W9JBvoHNXHntFlGc71OM10UYTt5QFy4X9hs_vkYe0J_F3ns91aNshXSw57eYWpu_NRW9qZKAMkWTdnvZgE9qeQtKLIt-k7PlntY7Csa0rmVOXae7rR1kECrZzwADPE47anVRniHLSjuM3gbrPytfej_cMmMJgKt10EsXnQiBsUN3DSbGbHE87zdtbI8-OY4-TgqJVj4yhuH7e2wc_RYEGOTEhQKN8wKMMWOMCMXKfKczJ-BnQWzv8N7Myc59pDnI8qV1aup7PXbT5qPavKME1OvaggLtBRT2eVf4whzl-3XyumujIZ_Wp0VQ5xPqRCm8UbSIc470idzYSa-rlY23y2OH0rxXOjb8REuLX1kMyURmqo1VSnqxH5OM4J55c6JfejeaTk_hCK6_uBH3j2RzMa-Df0A7WrlTNa1m2eUVeitSLrq6lQ5N9czyCJl38D) |
| 3b | `{ service: 1, level: 1, duration_ms: 1, ts: -1 }` | 33 | 33 | 33 | `IXSCAN → FETCH → SORT` | [Plan 3b](https://dfrancour.dev/tools/mongodb-paste-the-plan?utm_source=chatgpt.com#v1:7VZLb9s4EP4rwaCHPaiBFMdxolv82gapazdy94E0MMbiSGFNkSpJOXYD__cFKT_TTVJ0L7vAniQO5xvO45vBPAItSoFc_kbacCUhhggC-FqRXo4ESkka4keQWJApMSWIQajcHNOcpDUQAJeMFn0uLOmELMQZCkMBlKgNsY_OjMO_Qckgvn0EQXMSXkJfIQbSWmlYrYJHMKTn3D2wuStxWfhH_DWrNFqu5KQwXiW3EDfDcLW6W63dfYfmHmLotKPTZu-8CwGUAmUH03u6piXE0O23oyjqtSEAVVpe8G_e4pgXNOBCcANxGECBiysXE7GhTpSonIq5IWeGbcPbKV1K9pJWkqI0Y9VblEIxeqrwwKXkMneJdkEZi7nLcL837rzzuS0rm9TC3W0yvBlDAEZpO0JrSXusNRC_jVYBFFS85wW3EEfh6XmzdRaGAdhl6aCMMqyEfdb01R9J5_IDBDCj5Z7tbWmiYFPAKDisSBTsPPCU-ICFs7iGTqKJB06iyR5sEk2smbx1hONmUAnLfaE22VsLRmjvzYEbt3dbP9zvgSNOYP3XeWI-Sf61oq1NbhLPzD3BCLXlKHYS5_22G04CYFxTauveyJR-QM02vG-rSrInvsHt5y11P0NwtH-6gz3PnaLnf621_vUqhxHBL80wDI64zI5Df-3jg9sBLq5pGRwNuLym5R3crVarVQCavlBqiTlWbRJBC0o9RxOL1ju8k1RpSsZAbHVFAcgbspWWjqSNxh7wSZdYZVFc09L0FljwrboXd1X6RLz_fE7m77j--rs9Y3mBlvz7D0rPDMRn5wEgm6NMN0BJxBwG4sZpffqTk2AeZHBOLgG1CU3GKr0n4KY37NfU_i4CFJqQuRkznH6ptV9qzn9VNP9sUtQlRYsJ_0aJ0tb7FjlfK0Osy81s2zum5ELUBPG_xDzQKo05OfwLmdvOnp_LncvPc7kLfzp1_8_B_-Qc9IV70sGGaGbWBSvNmIwnclgfu1qVpT_XMzRVReFXlkfIuPvCduHJ_K5zEOtuVdlGtd5sguf3lrovDxrSzHjpXRJ1W9bbiOd9AvFZGLoGfcOm6yUMHIT0nPSVzJSzdK-MhRjOMsITTBEvWo5TpX_npBVGrQDm2z2vdRwenzYhgJzb3faHzZNG1KCogdNmM72YMpa10kaWXUQMpyfnZxk2zqPWxdnu8RFqLMiS9gFy6boFhV_9-piSbVdZRtp1f3tp3fDfmzbfaw9wMaxsWdmuSl_GvFdqVpV-jlw5UUGMo6WuSitXjAEuXsZvFBNV6ZR-1aoqB7gYUKH08hVPB7hoC5XOuMzdRKwxnwzmr4U40uqeT7ndoAekcxrKgZK5StbD8fCdS8bGKiH7o3EkZH_nkqmHvpt25kcj6rsaulHaUdJqJeoeT6kj0Bie9mTOJbmaqxnE0eov) |
| 4 без индекса | Без дополнительного индекса | 10 | 1200 | 0 | `COLLSCAN → SORT → LIMIT` | [Plan 4 без индекса](https://dfrancour.dev/tools/mongodb-paste-the-plan?utm_source=chatgpt.com#v1:tVRtb-M2DP4vxH30CttpXupvbZpsxTVLV3cbhmEYGIl2tciST5LT5A757wOVJk2vRXsbtk-WKZIP-TwUvwCtW43K_ELOK2uggAwS-NSR29xoNIYcFF_AYEO-RUFQgLa1P6EVmeAhAWUkradKB3IlBSgq1J4SaNF5kj9xGo7XtCLNhw_0CQog56yD7fYR6Af091BAf5IPeqf9CSTQajRjFPf0kTbPb2wbVKM-Y1DW3KmGZkpr5aFIE2hwfcXVkJy70uqOXfwtcRp5KOzJ6dzIt7xKgcbf2cm61VbS1w4PyhhlaqaI2_IBa-amnN_eQQLeunCDIZCLt7Jzsd4_Gw_Fd9k2gYaaa9WoAEWWno76w0GaJqDZct7YzkR7AmHTclKvmlZT5LrtQrmDesIcz6-vy_H5j5BAFXV4k3CpHImwU7qy7gGdjHZHf5EIJLkjD8Xvf2wToDWJyE8ZMHjO9mTphCDvoQiuowTMLYXOGSaICz-4faVQsAH1R9r4yRobFd331ksrjqxZnqbP8WvyrxD9Pu7EB9VgoIj0YN3Sc_YsTwDlCo3YhxoiyVERO9v9_6ZI70r0uCImga-ZKx-sOzIoP5lP4-l_Un5HEQYs1WcqrQtcdj7Kewl0nuSl8svDaPpWab3jOx5JxsBgHdbE8fHqv5ilY_ZH_4R-JviI_tFz_tM8_df8vzbeCcgXw7Xl-oVtGjSSW6sUf-Gw1l50v297J_Hr2vqlamO5eq9w3CSRjRKKQZqy2B_k4nGLxmzkVuSuTGU55731AQoYVIQ5CsSzIW_jNiLmwzQbJrA6LOrhSXpy2ocEahWe1jf2817Wo6yHi35fnC2krIaiV1VnmcRFPhpU2Btlw7PBE_gNOmwokIsvTBkeXtRxd09RULjoqoocT87FJvAzPJrcl94zXM-70Hbh0oq3Y66tXXZtnMErNjUkFQa6tKJryHCit-P3jqXtnKDvne3aGa5n1Fi3eafSGa4vtBVLZWp-TbuYnz3W77V44-y9Wqiwj56Rq2luZtbUtnx8WM9xzqW8syWFb-2jpPCrMtI-THn6_bd2NGUN-YGNrQnO6t38Cxpr9F6JiamVIdbcLqHItn8D) |
| 4 с индексом | `{ level: 1, duration_ms: -1 }` | 10 | 10 | 10 | `IXSCAN → FETCH → LIMIT` | [Plan 4 с индексом](https://dfrancour.dev/tools/mongodb-paste-the-plan?utm_source=chatgpt.com#v1:7VXJcts4EP2VVFeOjIuULMnmzdomKoexEiqzlONytYimhAgEaACUqaT071OA1sgzdmY5zGFOEpqv0ct76P4GVJcCufyZtOFKQgwRBPBQkV6NBUpJGuJvILEgU2JGEINQM3NGS5LWQABcMqqHXFjSKVmIcxSGAihRG2If3DXOX9CShPvzmh4gBtJaaVivt4HeoplDDK1Bo908bw0ggFKg7GE2p2taQQzd5qDfvWj3IQBVWl7wr2i5khNeUMKF4AbiMIAC65HLhtiNTpWoHMR8JHcN2yd2AF1J9hwqzVCaiRrUpVCMTgGPXEouZ65FrixjceZ6826UjCYQgOAFt1eFqqSFOApdm8rKphvUAT4cTHpv4c--jn5Ne1fvIYAFrcZoLWl51MsoAFZp34f7wkD8Jlpv2XiPhefJ4e6j-yPU_RtHLjdJJSz3rd3VuzWM0c7NUZDbu5Mot3cuivkk-UNFe3duUk_4kWGM2nIUB4vLbC-yRgCMa8rsRnK50o-o2U5OXVVJ9l0acPt5I5rPELza_72DJ-nBbYL1Na2CVwmX17S6g7v12glN0xfKLDHH2K4Oqinz_KcWrY93sFRZRsZAbHVFAciPZCstnQAcm3vYiQKtsiiuaWUGNRZ8D_fmvspOzMfhZ2T-SEcvxx0Yywu05OM_Kr0wEEdRAMiWKLOdoyRizsej3OE3ToL5k8Elufo33zQZq_SRgZvBzdCr7S9q-m-mHv7rqYcBsCe9R6EJmZs8N9MvG_Tzb_C_VM7_8-AfzQPfwBM9GCLPl_MvzYSMpQ0p7tjXqiz9eTNLMlUUKJlLKOfuF_brMPeb8CjV3a4LwCht3YenLJkFL30w_8Q2CRVYe2mlELfDMAwDeM2m2-3rbyO9JD2SuXJ3zpWxEEM7J2xghnjZccSWPmKjE0adAJb7Bd85C8_OWxDAjNvD2sdWoxk1KWritNXKLqeM5Z2smeeXEcNp46KdY_Mi6ly2D8HHqLEgS9pTw6UTJAq_84eYke1WeU465V-pu7LkX8P5RavTDv1rO0UnWN9UtqxsX2XP-7xTalGV_qmOnKkgxtFSX2VVQdJd9Lz_DpiqSmf0k1ZVmWCdUKH06oVME6y7QmULLmep0nbj88ng7KUSx1rN-ZTbnXdCekY3MlFyptLt_Pk-zhVjE5WS_dE6UrK_cMnU49ANFPOjFQ0dh25a9ZS0WonN68uoJ9AYng3kjEtynKsFxNH6dw) |


## 5. Анализ результатов

По результатам экспериментов можно сделать следующие наблюдения.

1. **Запрос без подходящего индекса требует сканирования коллекции.** В первом эксперименте проверяется до 1200 документов, хотя возвращается только 33 документа.

2. **Составной индекс уменьшает объём чтения.** В плане 2 количество просмотренных документов сокращается до 33. Это уменьшает объём работы по сравнению с полным сканированием коллекции.

3. **Порядок полей в составном индексе имеет значение.** Индекс с полем диапазона на первом месте может просматривать больше ключей и не обеспечивать нужный порядок сортировки.

4. **Поля точного совпадения полезно размещать перед полем диапазона.** В сравнении планов 3a и 3b ожидаемое количество просмотренных ключей уменьшается с 378 до 33. При этом сортировка по `ts` остаётся отдельным этапом.

5. **Индекс может одновременно ускорять фильтрацию и сортировку.** В плане 4 индекс `{ level: 1, duration_ms: -1 }` подходит для поиска по `level` и сортировки по `duration_ms`. Это позволяет получить первые десять результатов без полного сканирования коллекции и отдельной сортировки.

6. **`limit(10)` сам по себе не гарантирует минимального количества проверок.** Без подходящего индекса серверу может потребоваться обработать большое количество документов, чтобы определить десять первых результатов после фильтрации и сортировки.

## 6. Вывод

В ходе практической работы был изучен метод `explain("executionStats")` и проведено сравнение планов выполнения запросов MongoDB с различными индексами.

Эксперименты показали, что подходящий индекс способен значительно уменьшить количество просматриваемых документов и ключей. При этом важен не только сам факт наличия индекса, но и порядок полей в составном индексе. Для эффективной сортировки индекс должен соответствовать условиям фильтрации и требуемому порядку сортировки.

Также было установлено, что ограничение количества результатов через `limit()` не всегда избавляет от полного сканирования коллекции. Если фильтрация и сортировка поддерживаются индексом, MongoDB может находить необходимые результаты значительно эффективнее.

Таким образом, анализ `executionStats` и `winningPlan` позволяет обоснованно оценивать эффективность индексов и выбирать структуру индекса в соответствии с конкретными запросами.

## 7. Файлы результатов

Планы выполнения сохранены в JSON-файлах:

- `plan-1.json`
- `plan-2.json`
- `plan-3a.json`
- `plan-3b.json`
- `plan-4-bez.json`
- `plan-4.json`


