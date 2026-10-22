from contextlib import ExitStack
from pathlib import Path

from conclude import conclude
from searcher import run_research


ROOT = Path(__file__).resolve().parent
html_folder = ROOT / "html"
json_folder = ROOT / "json"
result_folder = ROOT / "search_result"
jev_result_folder = ROOT / "jev_result"


def main():
    from html_reader import html2json

    json_folder.mkdir(exist_ok=True)
    result_folder.mkdir(exist_ok=True)
    html_files = sorted(path for path in html_folder.iterdir() if path.suffix.lower() in {".html", ".htm"})
    for index, html_file in enumerate(html_files, 1):
        json_file = json_folder / f"{html_file.stem}.json"
        print(f"[Parse {index}/{len(html_files)}] {html_file.name}", flush=True)
        html2json(html_file, json_file, watermark=html_file.stem)
        print(f"Parsed -> {json_file}", flush=True)

    json_files = sorted(json_folder.glob("*.json"))
    candidate_counts = {}
    for index, json_file in enumerate(json_files, 1):
        print(f"[Regex file {index}/{len(json_files)}] {json_file.name}", flush=True)
        matches = run_research(json_file, result_folder / json_file.name, use_jev=False)
        candidate_counts[json_file] = len(matches)

    with ExitStack() as resources:
        model = None
        for index, json_file in enumerate(json_files, 1):
            print(f"[Jev file {index}/{len(json_files)}] {json_file.name}", flush=True)
            if model is None and candidate_counts[json_file]:
                from jev.local_jev import JevModel
                print("[Jev] Loading shared model on cuda ...", flush=True)
                model = resources.enter_context(JevModel(device="cuda"))
            run_research(result_folder / json_file.name, jev_result_folder / json_file.name, model=model)

    jev_result_folder.mkdir(exist_ok=True)
    conclude(jev_result_folder, ROOT / "result.json")


if __name__ == "__main__":
    main()
