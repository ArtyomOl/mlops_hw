# Базовая модель против адаптера

Адаптер: `models/adapter_all_layers`. Генерация жадная, до 40 токенов.

## 1. What does their system consist of?

**База:**

> Their system consists of rule-based and dictionary-based methods combined (in a way we prefer to call resource-based).

**Адаптер:**

> rule-based and dictionary-based methods combined (in a way we prefer to call resource-based)

## 2. How many different characters were in dataset?

**База:**

> The number of different characters in the dataset is 45,821.

**Адаптер:**

> 45,821

## 3. What baseline models are used?

**База:**

> The baseline models used are Kvmemnn, Feed Yourself, Poly-encoder, and a BERT bi-ranker baseline trained on the Persona-Chat dataset.

**Адаптер:**

> Kvmemnn, Feed Yourself, Poly-encoder, and a BERT bi-ranker baseline trained on the Persona-Chat dataset using the same training hyperparameters (including learning rate scheduler and length

## 4. Where do they obtain the news videos from?

**База:**

> They obtain the news videos from the NowThisNews Facebook page.

**Адаптер:**

> NowThisNews Facebook page

## 5. What two large datasets are used for evaluation?

**База:**

> The two large datasets used for evaluation are SParC BIBREF2 and CoSQL BIBREF6.

**Адаптер:**

> SParC BIBREF2; CoSQL BIBREF6
