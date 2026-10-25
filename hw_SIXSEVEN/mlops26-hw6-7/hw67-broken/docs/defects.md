# Четыре дефекта части A

1. Общий all-candidates run смешивал параметры и метрики моделей; условие log_params скрывало различия. Исправление: отдельный nested run внутри цикла и безусловный log_params. Доказательство: 6 runs в sweep, comparison.csv и проверки 1/3 tests/check.py.

2. Postgres переживал замену контейнера, но /mlartifacts лежал в слое контейнера. Исправление: именованный volume artifacts:/mlartifacts. Доказательство: storage-check.json, run 3f2a8c26f0bc4f438e9d9a87dfd0e65c, SHA256 ad2ffa6017a6428b71a9f75df640694079fd57fce2341a7a7389cff7fb33372b; проверка 8.

3. provenance вычислял data_train_sha256/data_val_sha256, но sweep отбрасывал их. Исправление: передаём полный provenance родительскому и каждому дочернему run. Доказательство: одинаковые актуальные хеши в tags всех runs, проверки 2 и src.promote.select.

4. promote вычислял val/base, но не вызывал gate до регистрации и смены alias. Исправление: gate(run, threshold) первым действием; отказ до любой записи в реестр. CLI src.promote создаёт только candidate; champion назначает evaluation.cli после качества. Доказательство: проверка 6 задаёт нулевой loss-порог и ожидает ValueError; negative-gate.json отдельно подтверждает отказ на повреждённых ответах.

Доказательства перечислены по созданным артефактам. Сам факт генерации этого отчёта не означает прохождения tests/check.py; итог 9/9 нужно получить отдельной проверкой.
