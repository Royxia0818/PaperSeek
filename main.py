import json
import re
from pathlib import Path

from conclude import conclude
from html_reader import html2json


html_folder = Path("html")
json_folder = Path("json")
result_folder = Path("result")


# 目标主题：注意力头之间、模态之间、或注意力头与模态之间的关系。
# 检索逻辑会在 title + abstract 中寻找这些概念，并进一步标注关系类型。
ENTITY_TERMS = {
    "attention_head": [
        "attention head",
        "attention heads",
        "multi-head attention",
        "multi head attention",
        "head-specific",
        "head specific",
        "heads",
    ],
    "modality": [
        "modality",
        "modalities",
        "multimodal",
        "multi-modal",
        "cross-modal",
        "cross modal",
        "unimodal",
        "audio-visual",
        "vision-language",
        "visual-language",
        "vision language",
        "visual language",
    ],
}


RELATION_TYPES = {
    "redundancy": [
        "redundan",
        "overlap",
        "duplicate",
        "prune",
        "pruning",
        "mask",
        "masking",
        "suppress",
        "suppressing",
        "unimportant",
        "not all",
        "only .* heads",
        "head selection",
        "selective",
        "sparse",
    ],
    "collaboration": [
        "collaborat",
        "cooperat",
        "synerg",
        "interact",
        "interaction",
        "fusion",
        "fuse",
        "joint",
        "complement",
        "mutual",
        "cross-modal",
        "cross modal",
        "aggregate",
        "aggregated",
    ],
    "expert": [
        "expert",
        "mixture-of-experts",
        "mixture of experts",
        "mixture-of-head",
        "mixture of head",
        "speciali",
        "specialized",
        "specialization",
        "route",
        "routing",
        "select .* heads",
        "token .* select",
        "functional pathway",
        "task-specific",
        "modality-specific",
        "head-specific",
    ],
    "interference": [
        "interfer",
        "conflict",
        "compete",
        "competition",
        "negative transfer",
        "imbalance",
        "disproportion",
        "suppress",
        "collapse",
        "hinder",
        "degrade",
        "harm",
        "bias",
        "dominant modality",
        "weak modality",
        "strong modality",
    ],
}


def normalize_text(*parts):
    return " ".join(part for part in parts if part).lower()


def matched_patterns(text, patterns):
    matches = []
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            matches.append(pattern)
    return matches


def make_snippets(text, patterns, window=90, limit=3):
    snippets = []
    seen = set()
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue

        start = max(match.start() - window, 0)
        end = min(match.end() + window, len(text))
        snippet = re.sub(r"\s+", " ", text[start:end]).strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet += "..."

        if snippet not in seen:
            snippets.append(snippet)
            seen.add(snippet)
        if len(snippets) >= limit:
            break
    return snippets


def classify_relation_papers(json_file, result_file):
    with open(json_file, "r", encoding="utf-8") as src_file:
        papers = json.load(src_file)

    results = {}
    for pid, info in papers.items():
        title = info.get("title", "")
        abstract = info.get("abstract", "")
        text = normalize_text(title, abstract)

        entity_hits = {
            name: matched_patterns(text, terms)
            for name, terms in ENTITY_TERMS.items()
        }
        entity_hits = {name: hits for name, hits in entity_hits.items() if hits}

        if not entity_hits:
            continue

        relation_hits = {
            name: matched_patterns(text, terms)
            for name, terms in RELATION_TYPES.items()
        }
        relation_hits = {name: hits for name, hits in relation_hits.items() if hits}

        # 必须能明确归到至少一种关系类型，避免只命中泛泛的 attention/multimodal 论文。
        if not relation_hits:
            continue

        matched_terms = []
        for hits in entity_hits.values():
            matched_terms.extend(hits)
        for hits in relation_hits.values():
            matched_terms.extend(hits)

        enriched_info = dict(info)
        enriched_info["matched_entities"] = sorted(entity_hits)
        enriched_info["matched_relation_types"] = sorted(relation_hits)
        enriched_info["matched_terms"] = sorted(set(matched_terms))
        enriched_info["match_snippets"] = make_snippets(
            f"{title}\n{abstract}",
            matched_terms,
        )
        results[pid] = enriched_info

    with open(result_file, "w", encoding="utf-8") as tgt_file:
        json.dump(results, tgt_file, indent=4, ensure_ascii=False)

    return results


json_folder.mkdir(exist_ok=True)
result_folder.mkdir(exist_ok=True)

for html_file in html_folder.iterdir():
    if html_file.suffix.lower() not in {".html", ".htm"}:
        continue
    json_file = json_folder / f"{html_file.stem}.json"
    html2json(html_file, json_file, watermark=html_file.stem)
    print(f"Parsed {html_file}")

total = 0
for json_file in json_folder.iterdir():
    if json_file.suffix.lower() != ".json":
        continue
    result_file = result_folder / json_file.name
    matches = classify_relation_papers(json_file, result_file)
    total += len(matches)
    print(f"Searched {json_file}: {len(matches)} matches")

merged = conclude(result_folder)
print(f"Total relation papers: {len(merged)}")
