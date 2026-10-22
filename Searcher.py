"""Single-file regex matching and optional in-process Jev filtering."""
import json
import math
from pathlib import Path
import re
import time

INTERPRETABILITY_TERMS = [r"\binterpret\w*\b"]
FILTER_FIELDS = {"match_snippets", "jev_topic", "jev_yes_probability"}
JEV_QUESTION = (
    'Does this paper belong to the research topic "interpretability for model editing"? '
    'Answer yes when interpretability is used or studied to understand, locate, explain, '
    'guide, or evaluate targeted edits to a learned model\'s knowledge or behavior. '
    'Examples include causal tracing, knowledge localization, analysis of neurons, circuits, '
    'or representations to explain or improve model/knowledge editing, and mechanistic '
    'analysis of how model edits work. General interpretability without a connection to '
    'model editing is not enough. Model editing without an interpretability component is '
    'not enough. Editing images, videos, or documents is not model editing. '
    'Judge only from the supplied paper title and abstract.'
)


def run_research(input_file, output_file, *, use_jev=True, device="cuda", model=None, model_path=None):
    """Read one JSON, write one JSON, and return the written paper dictionary.

    Default: regex-match title/abstract, then keep Jev P(yes) > 0.5.
    use_jev=False writes regex matches only. Passing model reuses an existing
    JevModel; this function closes only a model that it loads itself.
    Neither mode adds screening metadata or writes any other result files.
    """
    input_file, output_file = Path(input_file), Path(output_file)
    if input_file.resolve() == output_file.resolve():
        raise ValueError("Output must not overwrite the input JSON file")
    with input_file.open("r", encoding="utf-8") as source:
        papers = json.load(source)

    candidates = {}
    print(f"[{input_file.name}] Scanning {len(papers)} papers ...", flush=True)
    for index, (pid, info) in enumerate(papers.items(), 1):
        title, abstract = info.get("title") or "", info.get("abstract") or ""
        # Scraped abstracts can contain the next article's metadata.
        boundary = re.search(r"(?i)\bPaperid\s*:\s*\d+", abstract)
        if boundary:
            tail = abstract[boundary.start():]
            if re.search(r"(?i)\bAuthors\s*:", tail) and re.search(r"(?im)^\s*Title\s*:", tail):
                abstract = abstract[:boundary.start()].rstrip()
        text = f"{title}\n{abstract}"
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in INTERPRETABILITY_TERMS):
            candidates[pid] = {key: value for key, value in info.items() if key not in FILTER_FIELDS}
            if abstract != (info.get("abstract") or ""):
                candidates[pid]["abstract"] = abstract
        if index % 500 == 0 or index == len(papers):
            print(f"[{input_file.name}] Fields {index}/{len(papers)} | candidates={len(candidates)}", flush=True)

    results = candidates
    if use_jev and candidates:
        owns_model = model is None
        results = {}
        try:
            if owns_model:
                from jev.local_jev import JevModel
                print(f"[Jev] Loading model on {device} ...", flush=True)
                started = time.perf_counter()
                model = JevModel(model_path, device=device)
                print(f"[Jev] Model ready in {time.perf_counter() - started:.2f}s", flush=True)
            started = time.perf_counter()
            for index, (pid, info) in enumerate(candidates.items(), 1):
                title, abstract = info.get("title") or "", info.get("abstract") or ""
                display_title = re.sub(r"\s+", " ", title)[:110]
                print(f"[{input_file.name}] Jev {index}/{len(candidates)} | {pid} | {display_title}", flush=True)
                try:
                    inference_abstract = abstract
                    while True:
                        try:
                            probability = float(model.yes_no({"title": title, "abstract": inference_abstract}, JEV_QUESTION))
                            break
                        except ValueError as exc:
                            if "Prompt exceeds context limit" not in str(exc) or not inference_abstract:
                                raise
                            # The model checks the full prompt's token count before
                            # inference. Shorten only the inference copy until it fits;
                            # keep the complete title, question and saved abstract.
                            previous_length = len(inference_abstract)
                            inference_abstract = inference_abstract[:previous_length // 2]
                            print(
                                f"[{input_file.name}] TRUNCATE | {pid} | context limit exceeded; "
                                f"abstract {previous_length} -> {len(inference_abstract)} characters; retrying",
                                flush=True,
                            )
                    if not math.isfinite(probability) or not 0 <= probability <= 1:
                        raise ValueError(f"Invalid yes probability: {probability}")
                except Exception as exc:
                    raise RuntimeError(f"Jev inference failed for {input_file.name}, paper {pid}: {exc}") from exc
                keep = probability > 0.5
                if keep:
                    results[pid] = info
                elapsed = time.perf_counter() - started
                eta = elapsed / index * (len(candidates) - index)
                print(
                    f"[{input_file.name}] {'KEEP' if keep else 'DROP'} | P(yes)={probability:.6f} "
                    f"({probability:.2%}) | {index}/{len(candidates)} ({index / len(candidates):.1%}) "
                    f"| kept={len(results)} | elapsed={elapsed:.1f}s | ETA={eta:.1f}s",
                    flush=True,
                )
        finally:
            if owns_model and model is not None:
                model.close()
    elif use_jev:
        print(f"[{input_file.name}] No field matches; skipping Jev.", flush=True)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_file.with_name(output_file.name + ".tmp")
    try:
        temporary.write_text(json.dumps(results, indent=4, ensure_ascii=False), encoding="utf-8")
        temporary.replace(output_file)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"[{input_file.name}] Saved {len(results)} papers -> {output_file}", flush=True)
    return results

if __name__ == "__main__":
    run_research("search_result/ICML2026.json", "jev_result/ICML2026.json")
    run_research("search_result/NIPS2026.json", "jev_result/NIPS2026.json")
    run_research("search_result/CVPR2026.json", "jev_result/CVPR2026.json")
    run_research("search_result/ECCV2026.json", "jev_result/ECCV2026.json")
