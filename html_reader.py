from bs4 import BeautifulSoup
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def html2json(html_file, json_file, watermark=""):
    with open(html_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    result = {}

    if html_file.stem.upper().startswith(("NIPS", "NEURIPS")):
        current_pid = None
        for div in soup.find_all("div"):
            if div.get("id") == "section":
                pid_tag = div.find("span", id="pid")
                current_pid = None
                if not pid_tag:
                    continue
                current_pid = watermark + "_" + pid_tag.get_text().strip().replace(",", "")
                result[current_pid] = {}
                arxiv_pdf_fallback = ""
                for link in div.find_all("a", href=True):
                    href = link["href"].strip()
                    parsed = urlsplit(href)
                    if parsed.hostname not in {"arxiv.org", "www.arxiv.org"}:
                        continue
                    if parsed.path.startswith("/abs/") and parsed.path[5:]:
                        result[current_pid]["href"] = href
                        break
                    if parsed.path.startswith("/pdf/") and parsed.path[5:]:
                        identifier = parsed.path[5:]
                        if identifier.endswith(".pdf"):
                            identifier = identifier[:-4]
                        arxiv_pdf_fallback = urlunsplit(parsed._replace(path="/abs/" + identifier))
                if not result[current_pid].get("href") and arxiv_pdf_fallback:
                    result[current_pid]["href"] = arxiv_pdf_fallback
            elif div.get("id") == "title" and current_pid:
                title_link = div.find("a")
                if title_link:
                    result[current_pid]["title"] = title_link.get_text().strip()
                    # Keep the arXiv URL found in this paper's section header.
                    if not result[current_pid].get("href"):
                        result[current_pid]["href"] = title_link.get("href", "").strip()
            elif div.get("id") == "abs" and current_pid:
                abstract = div.find("span", id="abs")
                if abstract:
                    result[current_pid]["abstract"] = abstract.get_text().strip()

    elif html_file.stem in ["ICML2025", "ICLR2025", "AAAI2025", "SIGGraph2025"]:
        divs = soup.find_all("div")
        current_pid = None

        for div in divs:
            if div.get("id") == "pid":
                pid_span = div.find("span", id="pid")
                if pid_span:
                    current_pid = watermark + "_" + pid_span.text.strip()
                    result[current_pid] = {}

            elif div.get("id") == "title" and current_pid:
                a_tag = div.find("a")
                if a_tag:
                    result[current_pid]["title"] = a_tag.text.strip()
                    result[current_pid]["href"] = a_tag.get("href", "").strip()

            elif div.get("id") == "abs" and current_pid:
                abs_span = div.find("span", id="abs")
                if abs_span:
                    result[current_pid]["abstract"] = abs_span.text.strip()
        
    elif html_file.stem in ["ICCV2025", "CVPR2025"]:
        divs = soup.find_all("div")
        current_pid = None
        
        for div in divs:
            if div.get("id") == "section":
                pid_tag = div.find("span", id="pid")
                if pid_tag:
                    pid_text = pid_tag.text.strip()
                    current_pid = watermark + "_" + pid_text.split(',')[0].strip()
                    result[current_pid] = {}

            elif div.get("id") == "title" and current_pid:
                a = div.find("a")
                if a:
                    result[current_pid]["title"] = a.text.strip()
                    result[current_pid]["href"] = a.get("href", "").strip()

            elif div.get("id") == "abs" and current_pid:
                span = div.find("span", id="abs")
                if span:
                    abstract_text = span.find(text=True, recursive=False).strip()
                    result[current_pid]["abstract"] = abstract_text
                    
    else:
        divs = soup.find_all("div")

        current_pid = None

        for div in divs:
            if div.get("id") == "section":
                pid_tag = div.find("span", id="pid")
                if pid_tag:
                    current_pid = watermark + "_" + pid_tag.text.strip().replace(",", "")
                    result[current_pid] = {}

            elif div.get("id") == "title" and current_pid:
                a = div.find("a")
                if a:
                    result[current_pid]["title"] = a.text.strip()
                    result[current_pid]["href"] = a.get("href", "").strip()

            elif div.get("id") == "abs" and current_pid:
                span = div.find("span", id="abs")
                if span:
                    result[current_pid]["abstract"] = span.text.strip()
                    
              
        
    with open(json_file, "w") as json_file:
        json.dump(result, json_file, indent=4)
        
    return result


if __name__ == "__main__":
    print(html2json(Path("html/ECCV2026.html"), Path("json/ECCV2026.json")))
