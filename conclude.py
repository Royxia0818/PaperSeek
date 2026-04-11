from pathlib import Path
import json

def conclude(result_folder:Path = Path("result")):
    result = {}
    
    for result_file in result_folder.iterdir():
        with open(result_file, "r") as json_file:
            new_data = json.load(json_file)
        result.update(new_data)

    with open("result.json", "w") as json_file:
        json.dump(result, json_file, indent=4)
    
    return result

if __name__ == "__main__":
    conclude()