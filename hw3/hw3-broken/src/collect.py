"""QASPER v0.3 → проверенные chat-примеры с текстовым подтверждением."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from src.config import load_params, source_files


def pick_prompt(example_id: str, variants: list[str]) -> str:
    digest = hashlib.sha1(example_id.encode("utf-8")).digest()
    return variants[int.from_bytes(digest, "big") % len(variants)]


def extract_answer(qa: dict, verify: bool) -> tuple[tuple[str, str] | None, str]:
    """Взять аннотацию, у которой каждый фрагмент ответа есть в evidence.

    Если несколько аннотаций подходят, выбираем самую короткую совокупность
    подтверждающих абзацев. Никаких ответов без проверяемого текста не создаём.
    """
    candidates: list[tuple[int, str, str]] = []
    has_extractive = False
    has_evidence = False
    for annotation in qa["answers"]:
        answer = annotation["answer"]
        if answer["unanswerable"]:
            continue
        spans = [span.strip() for span in answer["extractive_spans"] if span.strip()]
        evidence = [
            passage.strip()
            for passage in answer["evidence"]
            if passage.strip() and not passage.startswith("FLOAT SELECTED")
        ]
        if not spans or not evidence:
            has_extractive |= bool(spans)
            continue
        has_extractive = has_evidence = True
        passages: list[str] = []
        for span in spans:
            matches = [p for p in evidence if span.casefold() in p.casefold()]
            if verify and not matches:
                break
            passages.append(min(matches or evidence, key=len))
        else:
            context = "\n".join(dict.fromkeys(passages))
            candidates.append((len(context), "; ".join(spans), context))
    if not candidates:
        reason = "span_mismatch" if has_evidence else "no_evidence" if has_extractive else "non_extractive"
        return None, reason
    _, answer, context = min(candidates, key=lambda item: item[0])
    return (answer, context), "ok"


def main() -> None:
    params = load_params()
    cfg = params["collect"]
    prompts = cfg["system_prompts"]
    if len(prompts) < 3:
        raise SystemExit("collect.system_prompts: нужны хотя бы три варианта")
    sources = source_files(params)
    out = Path(params["paths"]["raw"])
    out.parent.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    groups: set[str] = set()
    used_prompts: set[str] = set()
    ids: set[str] = set()

    with out.open("w", encoding="utf-8") as dst:
        for source in sources:
            papers = json.loads(source.read_text(encoding="utf-8"))
            for paper_id, paper in papers.items():
                for qa in paper["qas"]:
                    counts["questions_scanned"] += 1
                    found, reason = extract_answer(qa, cfg["verify_answer_span"])
                    if found is None:
                        counts[f"dropped_{reason}"] += 1
                        continue
                    answer, context = found
                    example_id = qa["question_id"]
                    if example_id in ids:
                        counts["dropped_duplicate_id"] += 1
                        continue
                    ids.add(example_id)
                    prompt = pick_prompt(example_id, prompts)
                    used_prompts.add(prompt)
                    groups.add(paper_id)
                    row = {
                        "id": example_id,
                        "topic": paper_id,
                        "messages": [
                            {"role": "system", "content": prompt},
                            {
                                "role": "user",
                                "content": f"Paper: {paper['title']}\nEvidence: {context}\nQuestion: {qa['question']}",
                            },
                            {"role": "assistant", "content": answer},
                        ],
                    }
                    dst.write(json.dumps(row, ensure_ascii=False) + "\n")
                    counts["rows_written"] += 1

    metrics = {
        "version": cfg["version"],
        "source_files": len(sources),
        "groups": len(groups),
        "system_prompt_variants": len(used_prompts),
        **dict(counts),
    }
    target = Path(params["paths"]["metrics_collect"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"collect: {cfg['version']}, вопросов {counts['questions_scanned']}, "
        f"проверенных ответов {counts['rows_written']}, статей {len(groups)} → {out}"
    )


if __name__ == "__main__":
    main()
