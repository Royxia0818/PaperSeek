"""Download papers sequentially from Jev result JSON files, grouped by conference."""
import argparse
from http.client import HTTPException
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent


def sanitize_filename(filename):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', str(filename)).strip().strip('.')
    name = name[:120].rstrip(' .') or 'unnamed_paper'
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *[f'COM{i}' for i in range(1, 10)], *[f'LPT{i}' for i in range(1, 10)]}:
        name = '_' + name
    return name


def pdf_url(url):
    """Convert OpenReview forum/arXiv abstract URLs to PDF URLs, preserving IDs."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError('Missing paper href')
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        raise ValueError(f'Expected an HTTP(S) paper URL: {url}')
    host = parts.hostname.lower()
    if (host == 'openreview.net' or host.endswith('.openreview.net')) and parts.path.rstrip('/') == '/forum':
        parts = parts._replace(path='/pdf')
    elif host in ('arxiv.org', 'www.arxiv.org') and parts.path.startswith('/abs/'):
        parts = parts._replace(path='/pdf/' + parts.path[len('/abs/'):])
    return urlunsplit(parts)


def is_pdf(path):
    path = Path(path)
    if not path.is_file():
        return False
    with path.open('rb') as file:
        return b'%PDF-' in file.read(1024)


def download_pdf(url, save_path, *, timeout=60, retries=3):
    """Save a verified PDF atomically; failed transfers do not replace existing files."""
    save_path = Path(save_path)
    temporary = save_path.with_name(save_path.name + '.part')
    try:
        url = pdf_url(url)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        if is_pdf(save_path):
            print(f'SKIP existing PDF: {save_path}', flush=True)
            return True
        for attempt in range(1, retries + 1):
            try:
                print(f'Downloading ({attempt}/{retries}): {url}', flush=True)
                request = Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/pdf,*/*;q=0.8', 'Accept-Encoding': 'identity'})
                with urlopen(request, timeout=timeout) as response:
                    first = response.read(1024)
                    if b'%PDF-' not in first:
                        raise ValueError(f'Response is not a PDF (Content-Type: {response.headers.get("Content-Type", "unknown")})')
                    total = len(first)
                    progress_time = time.monotonic()
                    with temporary.open('wb') as target:
                        target.write(first)
                        while chunk := response.read(64 * 1024):
                            target.write(chunk)
                            total += len(chunk)
                            if time.monotonic() - progress_time >= 5:
                                print(f'  {save_path.name}: {total / 1024 / 1024:.1f} MiB received', flush=True)
                                progress_time = time.monotonic()
                    expected = response.headers.get('Content-Length')
                    if expected is not None and total != int(expected):
                        raise OSError(f'Incomplete response: received {total} of {expected} bytes')
                temporary.replace(save_path)
                print(f'SAVED {total / 1024 / 1024:.2f} MiB -> {save_path}', flush=True)
                return True
            except (OSError, URLError, HTTPException, ValueError) as exc:
                temporary.unlink(missing_ok=True)
                print(f'Download failed: {exc}', flush=True)
                # A forbidden or missing PDF needs a corrected link/access, not retries.
                if isinstance(exc, HTTPError) and exc.code not in (408, 429, 500, 502, 503, 504):
                    break
                if isinstance(exc, ValueError) or attempt == retries:
                    break
                time.sleep(min(2 ** (attempt - 1), 5))
    except (OSError, ValueError) as exc:
        print(f'Download failed: {exc}', flush=True)
    finally:
        temporary.unlink(missing_ok=True)
    return False


def download_json(json_file, output_folder, *, timeout=60, retries=3):
    """Download one paper dictionary into the supplied conference directory."""
    json_file, output_folder = Path(json_file), Path(output_folder)
    with json_file.open('r', encoding='utf-8') as source:
        papers = json.load(source)
    if not isinstance(papers, dict):
        raise ValueError(f'{json_file.name} must contain a dictionary keyed by paper ID')
    output_folder.mkdir(parents=True, exist_ok=True)
    counts = {'downloaded': 0, 'skipped': 0, 'failed': 0}
    for index, (pid, paper) in enumerate(papers.items(), 1):
        if not isinstance(paper, dict):
            counts['failed'] += 1
            print(f'[{json_file.name}] {index}/{len(papers)} FAILED | {pid}: invalid paper record', flush=True)
            continue
        title = str(paper.get('title') or pid)
        # The ID avoids collisions between different papers with the same title.
        identifier = sanitize_filename(str(pid).split()[0] if str(pid).split() else 'paper')[:40]
        filename = f'{identifier}_{sanitize_filename(title)}.pdf'
        destination = output_folder / filename
        print(f'[{json_file.name}] {index}/{len(papers)} ({index / len(papers):.1%}) | {pid} | {title}', flush=True)
        if is_pdf(destination):
            counts['skipped'] += 1
            print(f'SKIP existing PDF: {destination}', flush=True)
        elif download_pdf(paper.get('href'), destination, timeout=timeout, retries=retries):
            counts['downloaded'] += 1
        else:
            counts['failed'] += 1
        print(f'  Progress: downloaded={counts["downloaded"]}, skipped={counts["skipped"]}, failed={counts["failed"]}', flush=True)
    print(f'[{json_file.name}] Complete: {counts}', flush=True)
    return counts


def download_directory(input_folder=None, output_root=ROOT / 'download', *, timeout=60, retries=3):
    if timeout <= 0 or retries < 1:
        raise ValueError('timeout must be positive and retries must be at least 1')
    if input_folder is None:
        input_folder = ROOT / 'jev_results'
        if not input_folder.is_dir():
            input_folder = ROOT / 'jev_result'
    input_folder, output_root = Path(input_folder), Path(output_root)
    if not input_folder.is_dir():
        raise FileNotFoundError(f'Jev results directory not found: {input_folder}')
    files = sorted(input_folder.glob('*.json'))
    if not files:
        raise FileNotFoundError(f'No JSON files in {input_folder}')
    print(f'Input: {input_folder}\nOutput: {output_root}\nJSON files: {len(files)}', flush=True)
    totals = {'downloaded': 0, 'skipped': 0, 'failed': 0, 'failed_files': 0}
    for index, source in enumerate(files, 1):
        destination = output_root / sanitize_filename(source.stem)
        print(f'\n[File {index}/{len(files)}] {source.name} -> {destination}', flush=True)
        try:
            counts = download_json(source, destination, timeout=timeout, retries=retries)
        except (OSError, ValueError) as exc:
            totals['failed_files'] += 1
            print(f'FAILED JSON file {source.name}: {exc}', flush=True)
            continue
        for key, value in counts.items():
            totals[key] += value
    print(f'\nAll files complete: {totals}', flush=True)
    return totals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, help='Default: jev_results/; falls back to existing jev_result/')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'download')
    parser.add_argument('--timeout', type=float, default=60, help='Socket timeout in seconds (default: 60)')
    parser.add_argument('--retries', type=int, default=3, help='Maximum attempts per PDF (default: 3)')
    args = parser.parse_args()
    try:
        totals = download_directory(args.input_dir, args.output_dir, timeout=args.timeout, retries=args.retries)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 1 if totals['failed'] or totals['failed_files'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
