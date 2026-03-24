import requests
import os
import json
import re  # 引入正则表达式模块
from pathlib import Path
import shutil


def sanitize_filename(filename):
    """
    清理文件名，移除或替换 Windows 非法字符，并限制长度。
    """
    # 1. 替换掉 Windows 文件名中的非法字符: \ / : * ? " < > |
    # 我们将它们统一替换为下划线 _
    illegal_chars = r'[\\/:*?"<>|]'
    sanitized = re.sub(illegal_chars, '_', filename)
    
    # 2. (可选但推荐) 移除其他可能引起混淆的特殊符号，如 $ ^ 等
    # 如果只想保留 字母、数字、中文、下划线、空格、连字符(-) 和点(.)
    # 下面的正则会保留这些字符，移除其他所有字符
    # 注意：\u4e00-\u9fff 是中文范围
    sanitized = re.sub(r'[^\w\u4e00-\u9fff\s\-.]', '', sanitized)
    
    # 3. 去除首尾的空格和点 (Windows 不允许文件名以点或空格结尾)
    sanitized = sanitized.strip().strip('.')
    
    # 4. 如果文件名为空（例如原标题全是特殊字符），给一个默认名
    if not sanitized:
        sanitized = "unnamed_paper"
        
    # 5. 限制文件名长度 (Windows 路径最大 260 字符，文件名建议不超过 255)
    # 预留 .pdf 后缀的长度
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
        # 添加 User-Agent 防止被某些网站拦截
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


if __name__ == "__main__":
    # 建议加上 encoding='utf-8' 防止中文乱码
    with open("results.json", "r", encoding='utf-8') as json_file:
        data = json.load(json_file)
    
    output_folder = Path("Downloads")
    if output_folder.exists():
        shutil.rmtree(output_folder)
    output_folder.mkdir(parents=True, exist_ok=False)

    success_count = 0
    fail_count = 0

    for id, paper_data in data.items():
        paper_href = paper_data["href"]
        paper_title = paper_data["title"]
        
        # 【关键修改】清理文件名
        safe_title = sanitize_filename(paper_title)
        
        # 构建完整路径
        save_path = output_folder / f"{safe_title}.pdf"
        
        # 如果文件名过长导致路径超过 Windows 限制，Path 可能会报错，
        # 但 sanitize_filename 已经限制了文件名长度，通常能避免这个问题。
        
        print(f"处理论文: {paper_title[:30]}... -> {safe_title[:30]}...")
        
        if download_pdf(paper_href, save_path):
            success_count += 1
        else:
            fail_count += 1

    print("-" * 30)
    print(f"下载完成! 成功: {success_count}, 失败: {fail_count}")