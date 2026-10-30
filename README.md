# 论文检索与本地 Jev 筛选

从会议论文列表 HTML 中提取标题、摘要和链接，先用正则表达式筛选候选，再用本地 Jev 模型判断论文是否属于 **interpretability for model editing**，按 `searcher.py` 中的 `THRESHOLD` 保留文章（当前为 `P(yes) > 0.7`），最后合并结果并按会议下载 PDF。批量检索默认只处理文件名含 `26` 的文件。

HTML 数据来源于 [CV Paper Portal](https://hongsong-wang.github.io/CV_Paper_Portal/)。`jev/` 目录引用上游 [feder-cr/jev](https://github.com/feder-cr/jev)，并包含本项目添加的 Python 本地调用接口。数据来源与版权说明见文末[致谢](#致谢)。

## 1. 整体流程

```text
CV Paper Portal 的会议页面（手动保存 HTML）
                  ↓
                html/
                  ↓ html_reader.py
                json/
                  ↓ searcher.run_research(..., use_jev=False)
           search_result/       正则匹配结果
                  ↓ searcher.run_research(..., use_jev=True)
             jev_result/        Jev 判断后保留的文章
                ↙     ↘
    conclude.py         pdf_downloader.py
         ↓                     ↓
    result.json          download/会议名称/*.pdf
```

`main.py` 自动执行 HTML 解析、正则匹配、Jev 筛选和结果合并。PDF 下载通过单独命令运行。筛选阶段在本机运行模型，无需启动 `jev.exe` 或 HTTP 服务；获取 HTML、安装依赖、下载权重和 PDF 时需要网络。

## 2. 目录与文件

```text
论文检索/
├── README.md
├── main.py                     # 批量解析、筛选、合并
├── html_reader.py              # HTML → 论文 JSON
├── searcher.py                 # 单文件 run_research 接口
├── conclude.py                 # 合并 Jev 结果、去掉辅助字段
├── pdf_downloader.py           # 按会议逐篇下载 PDF
├── html/                       # 手动保存的原始会议页面
│   └── CVPR2026.html
├── json/                       # 从 HTML 提取的论文记录
│   └── CVPR2026.json
├── search_result/              # 正则筛选后的候选论文
│   └── CVPR2026.json
├── jev_result/                 # P(yes) > THRESHOLD 的论文
│   └── CVPR2026.json
├── result.json                 # 合并 jev_result/ 中所有 JSON
├── download/
│   └── CVPR2026/               # 该会议保留文章的 PDF
└── jev/
    ├── README.md               # 上游项目说明
    ├── LOCAL_INFERENCE.md      # 本地 Python 推理说明
    ├── local_jev.py            # 本地增补：JevModel 接口
    ├── scripts/setup_local.py  # 本地增补：安装、下载与校验
    ├── examples/local_inference.py
    ├── requirements-local.txt
    ├── requirements-local-gpu.txt
    ├── models/                 # 完整 GGUF 模型
    ├── runtime/jev/model/      # 可选：已有 OpenVINO 模型
    ├── runtimes/downloads/     # 安装包下载缓存
    └── .venv/                  # 项目 Python 环境
```

各 JSON 使用论文 ID 作为键，记录中通常包含 `title`、`href`、`abstract`。例如：

```json
{
    "CVPR2026_123": {
        "title": "Example Paper Title",
        "href": "https://example.org/paper.pdf",
        "abstract": "Example abstract."
    }
}
```

## 3. 环境与模型准备

以下命令面向 **Windows x64、Python 3.12、NVIDIA GPU**，均在项目根目录执行。当前使用 RTX 4060 Laptop GPU 8 GB 验证了 CUDA 推理。其他设备的部署细节参见 [Jev 本地推理说明](jev/LOCAL_INFERENCE.md)。

### 3.1 创建环境并安装依赖

```powershell
cd E:\Research\论文检索

# 已有 jev/.venv 时跳过这一行
python -m venv .\jev\.venv

# HTML 解析依赖
.\jev\.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple beautifulsoup4

# 下载模型、安装 GPU 推理包及 CUDA 运行库
.\jev\.venv\Scripts\python.exe .\jev\scripts\setup_local.py --gpu
```

直接使用虚拟环境中的 Python，无需激活环境，也无需替换 Conda base 中的 PyTorch。PDF 下载器使用 Python 标准库，不需要额外安装 `requests`。

安装脚本固定使用：

| 内容 | 当前版本或文件 | 存放位置 |
|---|---|---|
| 完整模型 | `jevos-v4-q8_0.gguf`，约 943 MB | `jev/models/` |
| CUDA Python 推理包 | `llama-cpp-python 0.3.36`，CUDA 12.4 Windows wheel | 安装到 `jev/.venv/` |
| CUDA Runtime | `nvidia-cuda-runtime-cu12==12.4.127` | 安装到 `jev/.venv/` |
| cuBLAS | `nvidia-cublas-cu12==12.4.5.8` | 安装到 `jev/.venv/` |
| OpenVINO Python 后端依赖 | 见 `jev/requirements-local.txt` | 安装到 `jev/.venv/` |

模型来自 [feder-cr/jev 的 jevos-v4 发布页](https://github.com/feder-cr/jev/releases/tag/jevos-v4)。上游 README 中可能使用 v5 示例；本项目当前安装脚本和默认 GPU 模型路径使用 **v4**，请以本地脚本为准。

CUDA 版推理包还需要 CUDA 12 运行库；只有显卡驱动或 CUDA Toolkit 11.8 时，并不包含这些 DLL。安装脚本会补齐运行库，`local_jev.py` 会注册项目内的 DLL 路径，无需修改系统 CUDA 配置。

`jev/runtimes/downloads/` 中是安装包缓存，环境安装完成后可以删除；之后重新执行安装脚本会重新下载缺少的缓存。正常推理依赖的 `jev/.venv/` 和 `jev/models/` 应保留。`tokenizer.gguf` 只是词表，不能替代完整 GGUF 模型。

### 3.2 验证本地推理

```powershell
.\jev\.venv\Scripts\python.exe .\jev\examples\local_inference.py --device cuda
```

输出中的 `device: cuda`、CUDA 设备信息及返回的概率表明示例已经运行。需要检查模型层卸载到 GPU 的日志时，追加 `--verbose`。

也可直接在 Python 中调用：

```python
from jev.local_jev import JevModel

with JevModel(device="cuda") as model:
    probability = model.yes_no(
        {"title": "Example title", "abstract": "Example abstract"},
        "Is this paper about interpretability for model editing?",
    )
    print(probability)
```

模型通过答案 token `0` 和 `1` 的 logits 计算二元判断概率，无需生成回答文本，因此 `output_tokens` 为 0。上游还支持多选和评分，本项目论文筛选使用其中的 `noul` 是非判断能力。

## 4. 准备会议 HTML

1. 打开 [CV Paper Portal](https://hongsong-wang.github.io/CV_Paper_Portal/)。
2. 进入需要的会议及年份页面。
3. 使用浏览器将页面保存为 HTML，放入 `html/`，保留原始页面内容。
4. 使用统一命名，例如 `CVPR2026.html`、`ECCV2026.html`、`ICML2026.html`、`NIPS2026.html`。

```powershell
New-Item -ItemType Directory -Force .\html | Out-Null
```

文件名的主体会成为 JSON 文件名和论文 ID 前缀，例如 `CVPR2026.html` 对应 `json/CVPR2026.json`。`html_reader.py` 对部分会议页面使用不同的解析分支，会议名与年份应沿用上述形式，不要写成 `CVPR26.html`。新增会议或页面结构变化时，需要核对解析结果。

程序不会自动从 Portal 下载 HTML；`html_reader.py` 读取的是本地保存的文件。

NIPS / NeurIPS 页面优先使用当前论文编号所在行的 arXiv `/abs/` 链接作为 `href`，例如 `https://arxiv.org/abs/2605.30332`，不会被标题上的 OpenReview 链接覆盖。该行只有 arXiv PDF 链接时会转换为 `/abs/` 保存；没有 arXiv 链接时回退到标题链接。

## 5. 运行完整筛选流程

```powershell
.\jev\.venv\Scripts\python.exe .\main.py
```

默认只处理文件名中含 `26` 的会议。可指定年份或进度打印间隔：

```powershell
# 2025 年；也可写 --year 25
.\jev\.venv\Scripts\python.exe .\main.py --year 2025

# 所有年份
.\jev\.venv\Scripts\python.exe .\main.py --year all

# 2026 年，每完成 50 篇 Jev 判断打印一次进度
.\jev\.venv\Scripts\python.exe .\main.py --year 2026 --progress-every 50
```

两位和四位年份都会转换为末两位，按文件名主体是否包含该字符串筛选；`all` 关闭年份筛选。

当前 `main.py` 的执行顺序为：

1. 解析 `html/` 中符合所选年份的 `.html`、`.htm` 文件，写入 `json/`。
2. 遍历 `json/` 中符合所选年份的现有 JSON，进行正则匹配，写入 `search_result/`。
3. 首次遇到候选文章时加载 GPU 模型，并在各会议间复用，写入 `jev_result/`。
4. 调用 `conclude.py`，合并 `jev_result/` 中符合所选年份的 JSON 到 `result.json`。

该入口处理所选年份的全部现有会议 JSON，不只处理本次新保存的 HTML。筛选结果按同名文件更新；PDF 不会在这个步骤中自动下载。

## 6. 单独处理一个文件或四个指定会议

### 6.1 单文件接口

`searcher.py` 的处理函数是 `run_research`：读取一个 JSON，写出一个 JSON，并返回结果字典。

```python
from searcher import run_research

# 只做正则匹配
run_research(
    "json/NIPS2026.json",
    "search_result/NIPS2026.json",
    use_jev=False,
)

# 对候选论文进行 Jev 筛选；默认使用 CUDA
run_research(
    "search_result/NIPS2026.json",
    "jev_result/NIPS2026.json",
)
```

默认 `use_jev=True`，会先检查正则，再进行模型判断。因此也可以直接将 `json/NIPS2026.json` 作为输入，但这一次调用只写指定的一个输出文件，不会额外生成正则结果或执行合并。

直接运行 `searcher.py` 会遍历 `search_result/` 中符合年份条件的候选文件，复用一个模型，将结果写入 `jev_result/`；不执行合并。默认年份为 `26`，同样支持 `--year 2025`、`--year all` 和 `--progress-every 20`。

```powershell
# 已有正则结果，只运行 Jev 筛选
.\jev\.venv\Scripts\python.exe .\searcher.py --year 2026
```

显式调用 `run_research(input_file, output_file)` 时，处理的是指定文件，不额外检查文件名年份。

### 6.2 只处理 NIPS2026、ICML2026、CVPR2026、ECCV2026

先确保对应的四个 `json/*.json` 已存在。在项目根目录的 PowerShell 中执行：

```powershell
@'
from pathlib import Path
from searcher import run_research
from jev.local_jev import JevModel
from conclude import conclude

conferences = ["NIPS2026", "ICML2026", "CVPR2026", "ECCV2026"]

for name in conferences:
    run_research(
        Path("json") / f"{name}.json",
        Path("search_result") / f"{name}.json",
        use_jev=False,
    )

with JevModel(device="cuda") as model:
    for name in conferences:
        run_research(
            Path("search_result") / f"{name}.json",
            Path("jev_result") / f"{name}.json",
            model=model,
        )

conclude()
'@ | .\jev\.venv\Scripts\python.exe -
```

这个示例复用同一个模型完成四个会议的筛选。最后的合并仍读取 `jev_result/` 下全部 JSON，因此该目录中已有的其他会议结果也会进入 `result.json`。

### 6.3 筛选规则与进度

| 步骤 | 当前规则 |
|---|---|
| 正则 | 在标题和摘要中匹配 `\binterpret\w*\b`，忽略大小写 |
| Jev | 判断论文是否将可解释性用于理解、定位、解释、指导或评价模型编辑 |
| 保留阈值 | `P(yes) > THRESHOLD`；当前 `THRESHOLD = 0.7`，恰好等于阈值时不保留 |
| 输出 | 保留论文记录，去掉 `match_snippets`、`jev_topic`、`jev_yes_probability` |

要修改检索主题，编辑 `searcher.py` 中的 `INTERPRETABILITY_TERMS` 和 `JEV_QUESTION`；要调整阈值，修改 `THRESHOLD`。正则是进入模型判断的前置条件：只出现其他同义表达、没有匹配该词族的论文不会进入 Jev，模型结果也需要结合实际论文复核。

如果希望任意标题、摘要都通过正则初筛，改为 `INTERPRETABILITY_TERMS = [r"[\s\S]*"]`。该表达式匹配任意字符（包括换行和空文本）；匹配对象仍是标题与摘要拼接后的文本，不会遍历其他 JSON 字段。

Jev 默认每完成 20 篇判断打印一次进度，并在当前文件完成时打印最后一次，例如 `Jev 20/1000 | kept=5 | truncated=1`。不再逐篇打印标题、概率和保留/排除结果。单文件函数可通过 `progress_every=50` 修改间隔，批量命令使用 `--progress-every 50`。

对于已知的摘要拼接问题，筛选器会识别后续文章的 `Paperid / Authors / Title` 标记并清理相应尾部。完整提示超过模型的 8192 token 限制时，将用于推理的摘要逐次减半后重试，并在进度中的 `truncated` 统计已截断论文数；标题、判断问题保持完整，结果中不会用这一推理截断版本替换摘要。此时判断依据只是截断后的内容。

如需使用已准备好的 CPU OpenVINO 模型，可显式调用 `run_research(..., device="cpu")`；`main.py` 的批量入口当前固定使用 CUDA。

## 7. 单独合并结果

```powershell
.\jev\.venv\Scripts\python.exe .\conclude.py
```

该独立命令不调用模型，默认读取 `jev_result/*.json` 的全部年份，按论文 ID 合并到 `result.json`。`main.py` 会把所选年份传给合并函数；显式 Python 调用也可使用 `conclude(year="26")`。同一 ID 重复时，按文件名排序后较晚读取的记录覆盖先前记录。合并时会去掉三个辅助字段，即使输入是历史版本生成的带辅助字段记录也会清理；原 `jev_result/` 文件不会被改写。

## 8. 按会议下载 PDF

```powershell
.\jev\.venv\Scripts\python.exe .\pdf_downloader.py `
    --input-dir .\jev_result `
    --output-dir .\download
```

下载器逐个读取 JSON、逐篇下载，文件名包含论文 ID 和经过清理的标题。例如：

```text
jev_result/CVPR2026.json
        ↓
download/CVPR2026/CVPR2026_123_Example Paper Title.pdf
```

下载器会将 OpenReview 的页面链接：

```text
https://openreview.net/forum?id=jqykrG5xAb
```

转换为：

```text
https://openreview.net/pdf?id=jqykrG5xAb
```

对于 OpenReview，转换 `/forum` 路径，保留 ID 和其他查询参数；对于 arXiv，将 `/abs/2605.30332` 转为 `/pdf/2605.30332` 后下载。转换只用于请求 PDF，不修改输入 JSON 中的 `href`；其他网站的链接按原地址请求。

已有且带有 PDF 文件标识的目标文件会跳过；新文件先写 `.part`，检查 PDF 标识和响应长度后再保存。下载器打印逐篇进度和成功、跳过、失败统计；可重试的网络错误默认最多尝试 3 次，单次 socket 超时默认 60 秒。403、404 或返回 HTML 的链接会报告失败并继续处理其他文章。

```powershell
# 调整超时与重试次数
.\jev\.venv\Scripts\python.exe .\pdf_downloader.py `
    --input-dir .\jev_result --output-dir .\download --timeout 120 --retries 5
```

不指定输入目录时，下载器优先使用 `jev_results/`；该目录不存在时使用当前项目中的 `jev_result/`。建议像上面的命令一样显式指定。下载内容来自论文链接对应的站点，部分链接可能需要额外访问权限或已失效。

## 9. 致谢

### Jev / Jevos

感谢 [feder-cr/jev](https://github.com/feder-cr/jev) 提供 Jevos 模型、OpenVINO 推理实现、GGUF 发布文件及相关文档。本项目的 `jev/` 目录引用该仓库；其中 `local_jev.py`、本地安装脚本和本地推理示例是为当前论文筛选流程添加的适配代码。上游项目的许可证与第三方声明见 [jev/LICENSE](jev/LICENSE) 和 [jev/THIRD_PARTY_NOTICES.md](jev/THIRD_PARTY_NOTICES.md)，分发时应保留相应声明。

### HTML 数据来源与版权说明

感谢 Hongsong Wang 维护 [CV Paper Portal 页面](https://hongsong-wang.github.io/CV_Paper_Portal/)及其[源代码仓库](https://github.com/hongsong-wang/CV_Paper_Portal/)，本项目使用的会议列表 HTML 下载自该页面。

**Content sourced from [https://github.com/hongsong-wang/CV_Paper_Portal/](https://github.com/hongsong-wang/CV_Paper_Portal/)**

以下保留所提供的版权声明原文。原始页面内容及相关作品的权利归原作者或相应权利人所有，来源标注不替代声明中要求的许可。

> This webpage is protected by copyright laws. Without the written permission of the owner of this webpage, no individual or organization shall use the content of this webpage in any form. If there is a need to reprint the content of this webpage for non-commercial purposes such as learning, research, or personal sharing, the source must be clearly indicated as "Content sourced from [https://github.com/hongsong-wang/CV_Paper_Portal/]". The content must be kept intact, and no alteration or distortion of the original text is allowed. The owner of this webpage reserves the right to pursue legal liability for any unauthorized use of the content of this webpage. If you find these works useful, please cite the above works.
