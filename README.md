# SCAU 论文自动化排版工具

面向华南农业大学论文/报告格式的排版助手，支持将原始文档交由 AI 按规范拆分为 Markdown，再自动组装为标准 Word 文档。

> 当前状态：**半成品**。

---

## 功能概览

- 支持输入：`.docx / .md / .txt`
- 两种 AI 模式：
  - **网页手动模式**（推荐，免费）
  - **API 自动模式**（需配置 Key）
- 自动生成：封面、摘要、目录、正文、参考文献、致谢等
- Word 端后处理：三线表、图片居中、目录刷新、语言校正
- GUI 界面：拖拽导入、组件勾选、一键生成

---

## 运行环境（必须）

- **Windows 系统**
- **Microsoft Office（Word）必须安装**
  - 本项目通过 Word COM 自动化完成文档拼装与样式处理
  - **不支持 WPS**（WPS 不兼容 COM 自动化流程）
- **Pandoc**（用于 Markdown 与 Word 转换）

---

## Python 依赖

建议使用 Python 3.9+。

核心依赖（手动安装）：

- PyQt6
- pyperclip
- openai（仅 API 自动模式需要）
- pywin32（Word COM）
- python-docx（生成/维护参考样式模板时使用）

---

## 快速启动（GUI）

1. 安装依赖与 Pandoc，确保本机已安装 Microsoft Word。
2. 双击或运行：
   - `main_gui.py`
3. 拖拽论文文件到界面。
4. 选择模式：
   - 网页手动模式：根据弹窗提示粘贴 AI 输出
   - API 自动模式：先配置 API Key
5. 勾选需要的组件并点击【开始排版】。

默认导出到项目根目录的 `outputs/` 文件夹（支持导出 `.docx` / `.pdf`，也可同时导出）；也可在第三步手动选择导出目录。

---

## API 配置

- 通过 GUI 中的【⚙️ API 配置】按钮设置
- 配置会保存到 `api_config.json`
- 支持 OpenAI 兼容接口（含中转站）

---

## 目录结构说明

```
AutoFormatter/
│
├── assets/                 # 静态资源 (cover.docx, toc.docx, symbols.docx 等)
├── 原始资源/               # 脚本当前用不到的原始资源/备份（仅归档，不参与运行流程）
├── md/                     # 中间产物 markdown
├── temp/                   # 临时文件
├── 引导/                   # 新手教程图片
│
├── core/                   # [核心逻辑层]
│   ├── __init__.py
│   ├── preprocess.py       # AI 交互、文本清洗、Prompt 管理
│   ├── build_engine.py     # Pandoc + Word COM 组装与样式处理
│   ├── config_manager.py   # API 配置/主题配置读写
│   └── worker.py           # 后台线程（从 GUI 中剥离）
│
├── ui/                     # [界面展示层]
│   ├── __init__.py
│   ├── main_window.py      # 主窗口框架（只负责 UI 组装）
│   ├── dialogs.py          # 各类弹窗（API 设置 / 教程 / 网页模式）
│   ├── widgets.py          # 自定义控件（DropArea）
│   └── styles.py           # 主题/样式表管理
│
├── main.py                 # 程序入口（推荐运行）
├── main_gui.py             # 兼容入口（转发到 main.py）
├── build_reference.py      # 生成 Word 参考样式模板
├── prompt.txt              # AI 提示词模板
├── api_config.json         # API 配置（运行后自动生成/更新）
└── requirements.txt        # 依赖清单
```

---

## 注意事项

- **必须使用 MS Office Word**，WPS 不支持。
- 若 Word 弹窗阻塞 COM，可能导致构建失败，请先关闭所有 Word 弹窗后再试。
- AI 返回结果必须包含 `===FILE: xxx===` 分隔格式，否则无法拆分。

---

## 后续计划

- 打包为 `.exe`，提供免安装启动
- 优化样式引擎与异常恢复

---
