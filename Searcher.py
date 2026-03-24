import json


def filter_titles(papers_dict):
    new_dict = {}
    
    # 定义需要同时存在的关键词列表
    keywords = ["multimodal", "interaction"]

    for pid, info in papers_dict.items():
        title = info.get("title", "")
        title_lower = title.lower()
        
        # 检查是否所有关键词都在标题中
        if all(keyword in title_lower for keyword in keywords):
            new_dict[pid] = info

    return new_dict


if __name__ == "__main__":
    with open("json/CVPR2025.json", "r") as json_file:
        data = json.load(json_file)
    
    filtered_data = filter_titles(data)
    print(f"已筛选出{len(filtered_data)}条数据。")
    
    with open("results.json", "w") as json_file:
        json.dump(filtered_data, json_file, indent=4)