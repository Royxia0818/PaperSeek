from contextlib import ExitStack
from pathlib import Path

from conclude import conclude
from searcher import run_research


ROOT = Path(__file__).resolve().parent
html_folder = ROOT / "html"
json_folder = ROOT / "json"
result_folder = ROOT / "search_result"
jev_result_folder = ROOT / "jev_result"


def main(year="26", progress_every=20):
    from html_reader import html2json

    year = str(year).strip().lower()
    if year != "all" and (not year.isdigit() or len(year) not in (2, 4)):
        raise ValueError("year must be a two/four-digit year or all")
    if progress_every < 1:
        raise ValueError("progress_every must be positive")
    year = None if year == "all" else year[-2:]
    print(f"Filename year filter: {year if year is not None else 'all'}", flush=True)
    json_folder.mkdir(exist_ok=True)
    result_folder.mkdir(exist_ok=True)
    html_files = sorted(path for path in html_folder.iterdir()
                        if path.suffix.lower() in {".html", ".htm"}
                        and (year is None or year in path.stem))
    for index, html_file in enumerate(html_files, 1):
        json_file = json_folder / f"{html_file.stem}.json"
        print(f"[Parse {index}/{len(html_files)}] {html_file.name}", flush=True)
        html2json(html_file, json_file, watermark=html_file.stem)
        print(f"Parsed -> {json_file}", flush=True)

    json_files = sorted(path for path in json_folder.glob("*.json")
                        if year is None or year in path.stem)
    if not json_files:
        print("No matching JSON files; no results updated.", flush=True)
        return
    candidate_counts = {}
    for index, json_file in enumerate(json_files, 1):
        print(f"[Regex file {index}/{len(json_files)}] {json_file.name}", flush=True)
        matches = run_research(json_file, result_folder / json_file.name, use_jev=False,
                               progress_every=progress_every)
        candidate_counts[json_file] = len(matches)

    with ExitStack() as resources:
        model = None
        for index, json_file in enumerate(json_files, 1):
            print(f"[Jev file {index}/{len(json_files)}] {json_file.name}", flush=True)
            if model is None and candidate_counts[json_file]:
                from jev.local_jev import JevModel
                print("[Jev] Loading shared model on cuda ...", flush=True)
                model = resources.enter_context(JevModel(device="cuda"))
            run_research(result_folder / json_file.name, jev_result_folder / json_file.name, model=model,
                         progress_every=progress_every)

    jev_result_folder.mkdir(exist_ok=True)
    conclude(jev_result_folder, ROOT / "result.json", year=year)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Parse, search and filter papers for a filename year.")
    parser.add_argument("--year", default="26", help="Filename year: 26, 2026, or all (default: 26)")
    parser.add_argument("--progress-every", type=int, default=20, help="Print progress every N papers (default: 20)")
    args = parser.parse_args()
    if args.progress_every < 1:
        parser.error("--progress-every must be positive")
    selected_year = args.year.strip().lower()
    if selected_year != "all" and (not selected_year.isdigit() or len(selected_year) not in (2, 4)):
        parser.error("--year must be a two/four-digit year or all")
    main(year=args.year, progress_every=args.progress_every)
