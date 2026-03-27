from pathlib import Path
from html_reader import html2json
from searcher import json2result
from pdf_downloader import download_json
import shutil

html_folder = Path("html")
json_folder = Path("json")
result_folder = Path("result")

for html_file in html_folder.iterdir():
    json_file = json_folder/f"{html_file.stem}.json"
    html2json(html_file, json_file)
    print(f"Parsed {html_file}")
    
for json_file in json_folder.iterdir():
    result_file = result_folder/json_file.name
    json2result(json_file, result_file)
    print(f"Searched {json_file}")

output_folder = Path("Downloads")
if output_folder.is_dir():
    shutil.rmtree(output_folder)

for result_file in result_folder.iterdir():
    download_json(result_file, output_folder)
    print(f"Downloaded {result_file}")