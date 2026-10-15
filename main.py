import json
import re
from pathlib import Path

from conclude import conclude
from html_reader import html2json


html_folder = Path("html")
json_folder = Path("json")
result_folder = Path("result")


# 目标主题：模型编辑，以及知识编辑、事实编辑等相关表达。
# 检索逻辑会在 title + abstract 中寻找这些关键词。
MODEL_EDITING_TERMS = [
    r"\bmodel[\s-]+edit(?:ing|s|ed|ors?)?\b",
    r"\bknowledge[\s-]+edit(?:ing|s|ed|ors?)?\b",
    r"\bfact(?:ual)?[\s-]+edit(?:ing|s|ed|ors?)?\b",
    r"\b(?:language[\s-]+models?|llms?)[\s-]+edit(?:ing|s|ed|ors?)?\b",
    r"\bedit(?:ing|s|ed)?\s+(?:(?:the|a|an)\s+)?"
    r"(?:(?:large|pre[\s-]?trained|neural|language|multimodal|vision[\s-]+language)\s+)*models?\b",
    r"\bedit(?:ing|s|ed)?\s+(?:(?:the|a|an)\s+)?llms?\b",
    r"\bedit(?:ing|s|ed)?\s+(?:factual\s+)?knowledge\b",
    r"模型编辑",
    r"知识编辑",
    r"事实编辑",
]


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


def search_model_editing_papers(json_file, result_file):
    with open(json_file, "r", encoding="utf-8") as src_file:
        papers = json.load(src_file)

    results = {}
    for pid, info in papers.items():
        title = info.get("title", "")
        abstract = info.get("abstract", "")
        text = normalize_text(title, abstract)

        matched_terms = matched_patterns(text, MODEL_EDITING_TERMS)
        if not matched_terms:
            continue

        enriched_info = dict(info)
        enriched_info["matched_model_editing_terms"] = sorted(set(matched_terms))
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
    matches = search_model_editing_papers(json_file, result_file)
    total += len(matches)
    print(f"Searched {json_file}: {len(matches)} matches")

merged = conclude(result_folder)
print(f"Total model-editing-related papers: {len(merged)}")
