from bs4 import BeautifulSoup
import json
from pathlib import Path


def html2json(html_file, json_file):
    with open(html_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    result = {}

    # 把所有 div 按顺序取出来
    divs = soup.find_all("div")

    current_pid = None

    for div in divs:
        # 1️⃣ 如果是 section，记录 pid
        if div.get("id") == "section":
            pid_tag = div.find("span", id="pid")
            if pid_tag:
                current_pid = pid_tag.text.strip().replace(",", "")
                result[current_pid] = {}

        # 2️⃣ 如果是 title，存标题和链接
        elif div.get("id") == "title" and current_pid:
            a = div.find("a")
            if a:
                result[current_pid]["title"] = a.text.strip()
                result[current_pid]["href"] = a.get("href", "").strip()

        # 3️⃣ 如果是 abstract，存摘要
        elif div.get("id") == "abs" and current_pid:
            span = div.find("span", id="abs")
            if span:
                result[current_pid]["abstract"] = span.text.strip()

    with open(json_file, "w") as json_file:
        json.dump(result, json_file, indent=4)
        
    return