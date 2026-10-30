from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
FILTER_FIELDS = {"match_snippets", "jev_topic", "jev_yes_probability"}


def conclude(result_folder: Path = ROOT / "jev_result", result_file: Path = ROOT / "result.json", *, year=None):
    result_folder, result_file = Path(result_folder), Path(result_file)
    result = {}
    
    if not result_folder.is_dir():
        raise FileNotFoundError(f"Jev results directory not found: {result_folder}")
    if year is not None:
        year = str(year).strip().lower()
        if year != "all" and (not year.isdigit() or len(year) not in (2, 4)):
            raise ValueError("year must be a two/four-digit year or all")
        year = None if year == "all" else year[-2:]
    files = sorted(path for path in result_folder.glob("*.json")
                   if year is None or year in path.stem)
    for index, source in enumerate(files, 1):
        if source.resolve() == result_file.resolve():
            continue
        with source.open("r", encoding="utf-8") as json_file:
            new_data = json.load(json_file)
        for pid, info in new_data.items():
            result[pid] = {key: value for key, value in info.items() if key not in FILTER_FIELDS}
        print(f"[Merge {index}/{len(files)}] {source.name}: {len(new_data)} papers", flush=True)

    result_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = result_file.with_name(result_file.name + ".tmp")
    try:
        temporary.write_text(json.dumps(result, indent=4, ensure_ascii=False), encoding="utf-8")
        temporary.replace(result_file)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Merged {len(result)} papers -> {result_file}", flush=True)
    
    return result

if __name__ == "__main__":
    conclude()
