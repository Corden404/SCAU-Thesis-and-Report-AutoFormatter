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

输出文档将在保存路径生成 `.docx` 文件。

---

## API 配置

- 通过 GUI 中的【⚙️ API 配置】按钮设置
- 配置会保存到 `api_config.json`
- 支持 OpenAI 兼容接口（含中转站）

---

## 目录结构说明

- `main_gui.py`：主界面入口
- `preprocess.py`：AI 预处理与文本拆分
- `build_engine.py`：Word 组装与样式后处理
- `build_reference.py`：生成 Word 参考样式模板
- `prompt.txt`：AI 提示词模板
- `assets/`：封面、目录、声明等静态 Word 模板
- `md/`：AI 拆分后的 Markdown 产物
- `引导/`：新手教程图片

---

## 注意事项

- **必须使用 MS Office Word**，WPS 不支持。
- 若 Word 弹窗阻塞 COM，可能导致构建失败，请先关闭所有 Word 弹窗后再试。
- AI 返回结果必须包含 `===FILE: xxx===` 分隔格式，否则无法拆分。

---

## 后续计划

- 打包为 `.exe`，提供免安装启动
- 优化样式引擎与异常恢复
- 支持latex排版
- 支持导出为pdf格式

---
