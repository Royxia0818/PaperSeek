"""Single-file regex matching and optional in-process Jev filtering."""
import json
import math
from pathlib import Path
import re
import time

KEY_WORDS = [r"[\s\S]*"]
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
# JEV_QUESTION = (
#     'Does this paper belong to the research topic "continual learning"? '
#     'Answer yes when the paper studies how machine learning models continuously '
#     'acquire new knowledge, learn sequential tasks, classes, or domains, while '
#     'retaining previously learned knowledge and capabilities. '
#     'Examples include lifelong learning, incremental learning, task-incremental '
#     'learning, class-incremental learning, domain-incremental learning, and '
#     'methods for preventing or mitigating catastrophic forgetting during '
#     'sequential model updates. '
#     'Online learning, transfer learning, or multi-task learning without a focus '
#     'on sequential knowledge acquisition and knowledge retention is not enough. '
#     'Judge only from the supplied paper title and abstract.'
# )
THRESHOLD = 0.7

def run_research(input_file, output_file, *, use_jev=True, device="cuda", model=None, model_path=None,
                 progress_every=20):
    """Read one JSON, write one JSON, and return the written paper dictionary.

    Default: regex-match title/abstract, then keep Jev P(yes) > THRESHOLD.
    use_jev=False writes regex matches only. Passing model reuses an existing
    JevModel; this function closes only a model that it loads itself.
    Neither mode adds screening metadata or writes any other result files.
    Jev progress is printed every progress_every papers and at completion.
    """
    if not isinstance(progress_every, int) or progress_every < 1:
        raise ValueError("progress_every must be a positive integer")
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
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in KEY_WORDS):
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
            truncated_count = 0
            for index, (pid, info) in enumerate(candidates.items(), 1):
                title, abstract = info.get("title") or "", info.get("abstract") or ""
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
                            inference_abstract = inference_abstract[:len(inference_abstract) // 2]
                    if not math.isfinite(probability) or not 0 <= probability <= 1:
                        raise ValueError(f"Invalid yes probability: {probability}")
                except Exception as exc:
                    raise RuntimeError(f"Jev inference failed for {input_file.name}, paper {pid}: {exc}") from exc
                keep = probability > THRESHOLD
                if keep:
                    results[pid] = info
                truncated_count += int(inference_abstract != abstract)
                if index % progress_every == 0 or index == len(candidates):
                    print(f"[{input_file.name}] Jev {index}/{len(candidates)} "
                          f"| kept={len(results)} | truncated={truncated_count}", flush=True)
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
    import argparse
    from contextlib import ExitStack

    parser = argparse.ArgumentParser(description="Filter existing regex results with Jev.")
    parser.add_argument("--year", default="26", help="Filename year: 26, 2026, or all (default: 26)")
    parser.add_argument("--progress-every", type=int, default=20, help="Print progress every N papers (default: 20)")
    args = parser.parse_args()
    year = args.year.strip().lower()
    if year != "all" and (not year.isdigit() or len(year) not in (2, 4)):
        parser.error("--year must be a two/four-digit year or all")
    if args.progress_every < 1:
        parser.error("--progress-every must be positive")
    year = None if year == "all" else year[-2:]
    root = Path(__file__).resolve().parent
    files = sorted(path for path in (root / "search_result").glob("*.json")
                   if year is None or year in path.stem)
    if not files:
        parser.error("No matching JSON files in search_result/")
    with ExitStack() as resources:
        shared_model = None
        for index, source in enumerate(files, 1):
            print(f"[File {index}/{len(files)}] {source.name}", flush=True)
            if shared_model is None:
                from jev.local_jev import JevModel
                print("[Jev] Loading shared model on cuda ...", flush=True)
                shared_model = resources.enter_context(JevModel(device="cuda"))
            run_research(source, root / "jev_result" / source.name, model=shared_model,
                         progress_every=args.progress_every)
