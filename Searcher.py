import json


def json2result(json_file, result_file, keywords=["multimodal", "interaction"]):
    with open(json_file, "r") as src_file:
        papers_dict = json.load(src_file)
    
    new_dict = {}

    for pid, info in papers_dict.items():
        title = info.get("title", "")
        title_lower = title.lower()
        
        # 检查是否所有关键词都在标题中
        if all(keyword in title_lower for keyword in keywords):
            new_dict[pid] = info

    with open(result_file, "w") as tgt_file:
        json.dump(new_dict, tgt_file, indent=4)

        
    return 
