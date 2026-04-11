import requests
import os
import json
import re  # 引入正则表达式模块
from pathlib import Path
import shutil


def sanitize_filename(filename):
    illegal_chars = r'[\\/:*?"<>|]'
    sanitized = re.sub(illegal_chars, '_', filename)

    sanitized = re.sub(r'[^\w\u4e00-\u9fff\s\-.]', '', sanitized)
    
    sanitized = sanitized.strip().strip('.')
    
    if not sanitized:
        sanitized = "unnamed_paper"
        
    max_length = 250 
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
        
    return sanitized

def download_pdf(url, save_path=None):
    """
    下载PDF文件并保存。
    """
    try:
        print(f"正在下载: {url}")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'}
        response = requests.get(url, stream=True, timeout=10, headers=headers)
        
        # 检查请求是否成功
        if response.status_code == 200:
            # 【新增】简单检查内容类型，防止下载了 HTML 而不是 PDF
            content_type = response.headers.get('Content-Type', '')
            if 'application/pdf' not in content_type:
                # 有些服务器可能不返回 Content-Type，或者返回 application/octet-stream
                # 这里做一个宽松的判断，如果不是 pdf 且也不是流，可以打印警告
                # 但为了不打断流程，我们暂时只打印警告，继续尝试保存
                print(f"⚠️ 警告: 响应头 Content-Type 不是 application/pdf ({content_type})，但将继续尝试保存。")
            
            # 写入文件
            # 注意：save_path 此时应该已经是经过 sanitize 处理过的合法路径
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # 检查文件大小是否为 0
            if os.path.getsize(save_path) == 0:
                print(f"❌ 错误: 文件保存后大小为 0 KB，可能是链接无效或内容为空。文件路径: {save_path}")
                return False

            print(f"✅ 成功保存至: {os.path.abspath(save_path)}")
            return True
        else:
            print(f"❌ 下载失败，状态码: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return False


def download_json(json_file, output_folder):
    with open(json_file, "r", encoding='utf-8') as json_file:
        data = json.load(json_file)
    
    output_folder.mkdir(parents=True, exist_ok=True)

    success_count = 0
    fail_count = 0

    for id, paper_data in data.items():
        paper_href = paper_data["href"]
        paper_title = paper_data["title"]
        
        safe_title = sanitize_filename(paper_title)
        
        # 构建完整路径
        save_path = output_folder / f"{safe_title}.pdf"
        print(f"处理论文: {paper_title[:30]}... -> {safe_title[:30]}...")
        
        if download_pdf(paper_href, save_path):
            success_count += 1
        else:
            fail_count += 1

    print("-" * 30)
    print(f"下载完成! 成功: {success_count}, 失败: {fail_count}")


if __name__ == "__main__":
    output_folder = Path("Downloads")
    result_file = Path("result.json")

    if output_folder.is_dir():
        shutil.rmtree(output_folder)

    download_json(result_file, Path("Downloads"))