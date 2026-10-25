# ДЗ 6+7: выбор адаптера и качество ответов

Сравнено 6 отдельных законченных runs одного sweep `f10d51003a6a4ae680c630d02c2beae4`. Лучший run: `94a484907fdd4275ab911cb26b7eec06` (all-r8-high). Val loss: 0.94963209 → 0.46753150.

Бюджет каждой конфигурации: {"seed": 42, "max_steps": 4, "train_limit": 32, "val_limit": 8, "batch_size": 1, "grad_accum": 2, "eval_every": 2, "gradient_checkpointing": true}. Фиксированы база, train/val, seed и бюджет; менялись lr, r и target_modules. Четыре шага и восемь val-примеров позволяют выбрать учебного кандидата, но не доказывают устойчивого преимущества. Ресурсы и loss всех runs — в comparison.csv.

Время и память — короткие измерения в одном процессе. Первый запуск включает прогрев; MPS driver_allocated_memory включает кеши драйвера. Эти числа не являются независимым бенчмарком скорости или чистой памяти адаптера.

Baseline: `{"kind": "base", "name": "Qwen/Qwen3-0.6B", "revision": "c1899de289a04d12100db370d81485cdf75e47ca"}`. Candidate: `{"kind": "adapter", "name": "my-qwen-adapter", "version": "1", "run_id": "94a484907fdd4275ab911cb26b7eec06", "uri": "models:/my-qwen-adapter/1"}`.

Протокол закреплён до оценки: 2026-10-25T12:33:21.953231+00:00, SHA256 `9b24b74004709dba55a0cecb9c60b146fd5fcb62711aee86db8d7bf59fa90b7d`; golden: `509e13831ca4be5f6dcc1186caa15634206d1701558079558dc07f03a5d7c69f`. Один system prompt, do_sample=False, seed и лимит генерации для обеих версий. Expected не передавался модели. Полностью оценены только база и один кандидат.

Критические срезы закреплены до измерения в evaluation/params.json. numeric проверяет точные числа, где близкая формулировка не исправляет ошибочный результат; method проверяет выбор метода — основное содержание вопросов по NLP-статьям. dataset проверяет источники данных, metric — способы оценки.

Baseline: n=50, correct=49, valid=50, errors=0; accuracy=0.980000, format_rate=1.000000.
Candidate: n=50, correct=0, valid=0, errors=0; accuracy=0.000000, format_rate=0.000000.

- dataset: baseline n=20, correct=20, valid=20, errors=0; accuracy=1.000000, format_rate=1.000000; candidate n=20, correct=0, valid=0, errors=0; accuracy=0.000000, format_rate=0.000000.
- method: baseline n=15, correct=15, valid=15, errors=0; accuracy=1.000000, format_rate=1.000000; candidate n=15, correct=0, valid=0, errors=0; accuracy=0.000000, format_rate=0.000000.
- metric: baseline n=5, correct=5, valid=5, errors=0; accuracy=1.000000, format_rate=1.000000; candidate n=5, correct=0, valid=0, errors=0; accuracy=0.000000, format_rate=0.000000.
- numeric: baseline n=10, correct=9, valid=10, errors=0; accuracy=0.900000, format_rate=1.000000; candidate n=10, correct=0, valid=0, errors=0; accuracy=0.000000, format_rate=0.000000.

Срезы могут пересекаться; общий n считается по вопросам, а не суммой срезов.

Исправлены id: []. Потеряны id: ["qasper-mcq-001", "qasper-mcq-002", "qasper-mcq-003", "qasper-mcq-004", "qasper-mcq-005", "qasper-mcq-006", "qasper-mcq-007", "qasper-mcq-008", "qasper-mcq-009", "qasper-mcq-010", "qasper-mcq-011", "qasper-mcq-012", "qasper-mcq-013", "qasper-mcq-014", "qasper-mcq-015", "qasper-mcq-016", "qasper-mcq-017", "qasper-mcq-018", "qasper-mcq-019", "qasper-mcq-020", "qasper-mcq-021", "qasper-mcq-022", "qasper-mcq-023", "qasper-mcq-024", "qasper-mcq-025", "qasper-mcq-026", "qasper-mcq-027", "qasper-mcq-028", "qasper-mcq-030", "qasper-mcq-031", "qasper-mcq-032", "qasper-mcq-033", "qasper-mcq-034", "qasper-mcq-035", "qasper-mcq-036", "qasper-mcq-037", "qasper-mcq-038", "qasper-mcq-039", "qasper-mcq-040", "qasper-mcq-041", "qasper-mcq-042", "qasper-mcq-043", "qasper-mcq-044", "qasper-mcq-045", "qasper-mcq-046", "qasper-mcq-047", "qasper-mcq-048", "qasper-mcq-049", "qasper-mcq-050"].

Behavioral: baseline n=4, correct=3, valid=4, errors=0; accuracy=0.750000, format_rate=1.000000; candidate n=4, correct=0, valid=0, errors=0; accuracy=0.000000, format_rate=0.000000.

- behavior-format: valid=False, correct=False; raw="A".
- behavior-paraphrase: valid=False, correct=False; raw="A".
- behavior-refusal: valid=False, correct=False; raw="A".
- behavior-missing-evidence: valid=False, correct=False; raw="REFUSE".

Решение: **не принят**. Gate: Регрессия общей accuracy.

Отрицательная проверка: отказ, причина — Регрессия общей accuracy. Испорчена отдельная копия raw-ответов; реальные веса и aliases не менялись.

Проверка хранения: run `3f2a8c26f0bc4f438e9d9a87dfd0e65c`, probe SHA256 `ad2ffa6017a6428b71a9f75df640694079fd57fce2341a7a7389cff7fb33372b`. Файл получен после force-recreate контейнера; обычного restart недостаточно.

[Оценочный run MLflow](http://127.0.0.1:5006/#/experiments/2/runs/aa00d482199544e1aa299cf11aa31d68).

## Пять пар для ручного разбора

Ниже автоматическая подборка реальных ответов. Перед сдачей человек должен сверить evidence, разметку и добавить собственные комментарии.

### qasper-mcq-001

Paper: An analysis of the utility of explicit negative examples to improve the syntactic abilities of neural language models
Evidence: Since our focus in this paper is an additional loss exploiting negative examples (Section method), we fix the baseline LM throughout the experiments. Our baseline is a three-layer LSTM-LM with 1,150 hidden units at internal layers trained with the standard cross-entropy loss. Word embeddings are 400-dimensional, and input and output embeddings are tied BIBREF11. Deviating from some prior work BIBREF0, BIBREF1, we train LMs at sentence level as in sequence-to-sequence models BIBREF12. This setting has been employed in some previous work BIBREF3, BIBREF6.
Question: Which architecture is used as the fixed baseline language model?
Options:
A: a three-layer LSTM-LM
B: a convolutional language model
C: an encoder-only Transformer
choices: A, B, C, REFUSE.

Эталон: `A`. Источник: {"dataset": "QASPER v0.3", "source_file": "../../../hw3/hw3-broken/data/test.jsonl", "source_id": "818c89b11471a6ca4f13c838713864fdf282c2ca", "paper_id": "2004.02451", "transformation": "curated evidence-grounded MCQ; question clarified"}.

Baseline raw: "{\"answer\":\"A\"}"; valid=True, correct=True.

Candidate raw: "A"; valid=False, correct=False.

Неверный или невалидный ответ даёт 0. Содержательно верная фраза без строгого JSON также даёт 0 по заранее закреплённому контракту.

Разбор с помощью AI: В evidence прямо указан three-layer LSTM-LM, то есть вариант A. База возвращает валидный JSON с A. Кандидат возвращает A без объекта JSON: выбор варианта совпадает с эталоном, но формат нарушен, поэтому end-to-end score равен 0. Это пример регрессии выполнения инструкции при сохранении содержательного выбора.

### qasper-mcq-004

Paper: IIIDYT at SemEval-2018 Task 3: Irony detection in English tweets
Evidence: Out of 43 teams our system ranked 421st with an official F1-score of 0.2905 on the test set. Although our model outperforms the baseline in the validation set in terms of F1-score, we observe important drops for all metrics compared to the test set, showing that the architecture seems to be unable to generalize well. We think these results highlight the necessity of an ad-hoc architecture for the task as well as the relevance of additional information. The work of BIBREF21 offers interesting contributions in these two aspects, achieving good results for a range of tasks that include sarcasm detection, using an additional attention layer over a BiLSTM like ours, while also pre-training their model on an emoji-based dataset of 1246 million tweets.
Question: What official F1 score is reported on the test set?
Options:
A: 0.2905
B: 0.9205
C: 0.5290
choices: A, B, C, REFUSE.

Эталон: `A`. Источник: {"dataset": "QASPER v0.3", "source_file": "../../../hw3/hw3-broken/data/test.jsonl", "source_id": "78661bdd4d11148e07bdf17141cf088db4ad60c6", "paper_id": "1804.08094", "transformation": "curated evidence-grounded MCQ; question clarified"}.

Baseline raw: "{\"answer\":\"A\"}"; valid=True, correct=True.

Candidate raw: "A"; valid=False, correct=False.

Неверный или невалидный ответ даёт 0. Содержательно верная фраза без строгого JSON также даёт 0 по заранее закреплённому контракту.

Разбор с помощью AI: В evidence явно дан официальный F1-score 0.2905: верен A. В исходном фрагменте есть противоречивая запись ranked 421st out of 43, поэтому вопрос специально ограничен F1 и не использует место команды. База отвечает валидным JSON с A, кандидат — голой A. При оценке числа нельзя подменять проверку значения сходством слов; здесь провал связан именно с форматом.

### qasper-mcq-029

Paper: From Speech-to-Speech Translation to Automatic Dubbing
Evidence: We collected a total of 657 ratings by 14 volunteers, 5 Italian and 9 non-Italian listeners, spread over the 24 clips and three testing conditions. We conducted a statistical analysis of the data with linear mixed-effects models using the lme4 package for R BIBREF31. We analyzed the naturalness score (response variable) against the following two-level fixed effects: dubbing system A vs. B, system A vs. C, and system B vs. C. We run separate analysis for Italian and non-Italian listeners. In our mixed models, listeners and video clips are random effects, as they represent a tiny sample of the respective true populationsBIBREF31. We keep models maximal, i.e. with intercepts and slopes for each random effect, end remove terms required to avoid singularities BIBREF32. Each model is fitted by maximum likelihood and significance of intercepts and slopes are computed via t-test.
Question: How many volunteers provided ratings for the dubbing evaluation?
Options:
A: 657
B: 14
C: 24
choices: A, B, C, REFUSE.

Эталон: `B`. Источник: {"dataset": "QASPER v0.3", "source_file": "../../../hw3/hw3-broken/data/test.jsonl", "source_id": "32e78ca99ba8b8423d4b21c54cd5309cb92191fc", "paper_id": "2001.06785", "transformation": "curated evidence-grounded MCQ; question clarified"}.

Baseline raw: "{\"answer\":\"A\"}"; valid=True, correct=False.

Candidate raw: "A"; valid=False, correct=False.

Неверный или невалидный ответ даёт 0. Содержательно верная фраза без строгого JSON также даёт 0 по заранее закреплённому контракту.

Разбор с помощью AI: Нужно различать 657 оценок, 14 добровольцев и 24 клипа. Вопрос о добровольцах, значит верен B=14. База выбирает A=657 в корректном JSON: это фактическая ошибка при правильном формате. Кандидат тоже выбирает A, дополнительно нарушая JSON-контракт. Этот пример показывает, почему format rate 100% у базы ещё не означает accuracy 100%. Обе версии ошиблись, исправленного ответа здесь нет.

### qasper-mcq-046

Paper: Attention Optimization for Abstractive Document Summarization
Evidence: We conduct our model on the large-scale dataset CNN/Daily Mail BIBREF19, BIBREF1, which is widely used in the task of abstractive document summarization with multi-sentences summaries. We use the scripts provided by BIBREF11 to obtain the non-anonymized version of the dataset without preprocessing to replace named entities. The dataset contains 287,226 training pairs, 13,368 validation pairs and 11,490 test pairs in total. We use the full-length ROUGE F1 and METEOR as our main evaluation metrics.
Question: Which main evaluation metrics are used for document summarization?
Options:
A: full-length ROUGE F1 and METEOR
B: RMSE and Pearson correlation
C: accuracy and UAR
choices: A, B, C, REFUSE.

Эталон: `A`. Источник: {"dataset": "QASPER v0.3", "source_file": "../../../hw3/hw3-broken/data/test.jsonl", "source_id": "be7b375b22d95d1f6c68c48f57ea87bf82c72123", "paper_id": "1910.11491", "transformation": "curated evidence-grounded MCQ; question clarified"}.

Baseline raw: "{\"answer\":\"A\"}"; valid=True, correct=True.

Candidate raw: "A"; valid=False, correct=False.

Неверный или невалидный ответ даёт 0. Содержательно верная фраза без строгого JSON также даёт 0 по заранее закреплённому контракту.

Разбор с помощью AI: В последней фразе evidence названы full-length ROUGE F1 and METEOR: верен A. База возвращает валидный JSON с A; кандидат — A без JSON. Названия ROUGE/METEOR являются содержанием вопроса, а не scorer этой работы: правильность MCQ проверяется программно по метке. Сходство текста здесь не заменяет ни выбор варианта, ни соблюдение схемы.

### qasper-mcq-050

Paper: Gender Bias in Neural Natural Language Processing
Evidence: We use the English coreference resolution dataset from the CoNLL-2012 shared task BIBREF15 , the benchmark dataset for the training and evaluation of coreference resolution. The training dataset contains 2408 documents with 1.3 million words. We use two state-of-art neural coreference resolution models described by BIBREF2 and BIBREF1 . We report the average F1 value of standard MUC, B INLINEFORM0 and CEAF INLINEFORM1 metrics for the original test set.
Question: How many words does the coreference training dataset contain?
Options:
A: 13 million
B: 1.3 million
C: 2.4 million
choices: A, B, C, REFUSE.

Эталон: `B`. Источник: {"dataset": "QASPER v0.3", "source_file": "../../../hw3/hw3-broken/data/test.jsonl", "source_id": "b458ebca72e3013da3b4064293a0a2b4b5ef1fa6", "paper_id": "1807.11714", "transformation": "curated evidence-grounded MCQ; question clarified"}.

Baseline raw: "{\"answer\":\"B\"}"; valid=True, correct=True.

Candidate raw: "B"; valid=False, correct=False.

Неверный или невалидный ответ даёт 0. Содержательно верная фраза без строгого JSON также даёт 0 по заранее закреплённому контракту.

Разбор с помощью AI: Фрагмент различает 2408 документов и 1.3 million words. Вопрос о словах: B. База выдаёт {"answer":"B"}, кандидат — B. Содержательный выбор совпадает с эталоном, но строгий JSON отсутствует. Такой ответ нельзя автоматически исправить парсером после оценки: это изменило бы заранее закреплённый протокол. Для следующего эксперимента нужно обучать соблюдению схемы на отдельном dev-наборе.

## Ограничения

Golden содержит собственные MCQ по 50 отдельным статьям отложенного QASPER. Не подтверждены человеком: 50 из 50. Нельзя выдавать AI-проверку за человеческую. Индекс включает весь исходный train, а не только 32 примера обучения. Контроль ловит точные нормализованные совпадения и пересечения статей; он не гарантирует отсутствия всех смысловых утечек. В provenance.json сохранены хеши исходников, тензоров и кода токенизации и проверка id. Отложенная часть ДЗ 3 стала регрессионным golden, независимый финальный audit не выполнялся.

BLEU/ROUGE/BERTScore оценивают сходство текста: неверный факт может совпадать с эталоном по большинству слов, а краткий верный ответ — получить низкое сходство. MCQ scorer проверяет метку программно. Модель-судья полезна для полноты и обоснованности открытых ответов, но подвержена эффекту порядка, многословия, предпочтению стиля и ошибкам. Для judge нужны слепые A/B и B/A, фиксированная рубрика, сохранённые входы/вердикты и сверка с человеком; платный API здесь не использовался.

При отказе сохраняем candidate и прежний champion. Следующий шаг — разобрать ошибки на отдельном dev-наборе и повторить сопоставимый эксперимент, сохраняя пороги и историю baseline.
