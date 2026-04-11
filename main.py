from pathlib import Path
from html_reader import html2json
from searcher import json2result
from pdf_downloader import download_json
import shutil
from conclude import conclude

html_folder = Path("html")
json_folder = Path("json")
result_folder = Path("result")

for html_file in html_folder.iterdir():
    json_file = json_folder/f"{html_file.stem}.json"
    html2json(html_file, json_file, watermark=html_file.stem)
    print(f"Parsed {html_file}")
    
for json_file in json_folder.iterdir():
    result_file = result_folder/json_file.name
    json2result(json_file, result_file, keywords=["attention", "head"])
    print(f"Searched {json_file}")

print(len(conclude()))