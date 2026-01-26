import os
import subprocess
import win32com.client as win32
import pythoncom
import time
from datetime import datetime

# ================= 1. 配置与资源注册表 =================
class Config:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")
    MD_DIR = os.path.join(BASE_DIR, "md")
    TEMP_DIR = os.path.join(BASE_DIR, "temp")
    REF_DOC = os.path.join(BASE_DIR, "reference.docx")
    OUTPUT_DOCX = os.path.join(BASE_DIR, "Output_Document.docx")

    # Word 常量
    WD_PAGE_BREAK = 7
    WD_ALIGN_PARAGRAPH_CENTER = 1
    WD_ALIGN_ROW_CENTER = 1
    WD_AUTO_FIT_WINDOW = 2
    WD_BORDER_TOP = -1
    WD_BORDER_BOTTOM = -3
    WD_LINE_STYLE_SINGLE = 1
    WD_LINE_WIDTH_150PT = 12
    WD_LINE_WIDTH_075PT = 6
    WD_COLOR_BLACK = 0

# 组件注册表：定义所有可用的模块
# type: 'static' (Word文件) | 'md' (Markdown文件)
COMPONENT_REGISTRY = {
    "cover":       {"type": "static", "path": os.path.join(Config.ASSETS_DIR, "cover.docx"), "desc": "论文封面"},
    "cover_exp":   {"type": "static", "path": os.path.join(Config.ASSETS_DIR, "cover_exp.docx"), "desc": "实验报告封面"},
    "originality": {"type": "static", "path": os.path.join(Config.ASSETS_DIR, "originality_declaration.docx"), "desc": "原创性声明"},
    "abs_cn":      {"type": "md",     "path": os.path.join(Config.MD_DIR, "abstract_cn.md"), "desc": "中文摘要"},
    "abs_en":      {"type": "md",     "path": os.path.join(Config.MD_DIR, "abstract_en.md"), "desc": "英文摘要"},
    "symbols":     {"type": "static", "path": os.path.join(Config.ASSETS_DIR, "symbols.docx"), "desc": "符号说明"},
    "toc":         {"type": "static", "path": os.path.join(Config.ASSETS_DIR, "toc.docx"), "desc": "目录"},
    "body":        {"type": "md",     "path": os.path.join(Config.MD_DIR, "body.md"), "desc": "正文内容"},
}

# ================= 2. 核心构建器类 =================
class DocumentBuilder:
    def __init__(self):
        self._ensure_dirs()
        self.word_app = None

    def _ensure_dirs(self):
        if not os.path.exists(Config.TEMP_DIR):
            os.makedirs(Config.TEMP_DIR)

    def _pandoc_convert(self, input_md, output_docx):
        """调用 Pandoc 将 MD 转为 Docx"""
        if not os.path.exists(input_md):
            print(f"[Error] Markdown 文件未找到: {input_md}")
            return None

        cmd = f'pandoc "{input_md}" --reference-doc="{Config.REF_DOC}" -o "{output_docx}"'
        try:
            subprocess.run(cmd, shell=True, check=True)
            return output_docx
        except subprocess.CalledProcessError:
            print(f"[Error] Pandoc 转换失败: {input_md}")
            return None

    def _process_styles(self, doc):
        """样式后处理：图片居中 & 三线表 & 语言修正"""
        print("   -> [Style] 执行样式精修与语言校正...")

        # ==========================================
        # 新增：修复红色波浪线 (语言设置)
        # ==========================================
        try:
            # 2052 是 "中文(中国)" 的 Locale ID
            # 1033 是 "英语(美国)"
            doc.Content.LanguageID = 2052
            doc.Content.NoProofing = False  # 允许校对，但现在是按中文校对

            # 为了保险，直接关闭文档的拼写检查显示（眼不见为净）
            doc.ShowSpellingErrors = False
            doc.ShowGrammaticalErrors = False
        except Exception as e:
            print(f"   -> [Warning] 语言设置失败: {e}")

        # ==========================================
        # 原有逻辑：图片处理
        # ==========================================
        if doc.InlineShapes.Count > 0:
            for shape in doc.InlineShapes:
                shape.Range.ParagraphFormat.Alignment = Config.WD_ALIGN_PARAGRAPH_CENTER
                shape.Range.ParagraphFormat.FirstLineIndent = 0
                shape.Range.ParagraphFormat.CharacterUnitFirstLineIndent = 0

        # ==========================================
        # 原有逻辑：表格处理 (三线表)
        # ==========================================
        if doc.Tables.Count > 0:
            for tbl in doc.Tables:
                # 边框清除与重设
                tbl.Borders.Enable = False
                tbl.Borders(Config.WD_BORDER_TOP).LineStyle = Config.WD_LINE_STYLE_SINGLE
                tbl.Borders(Config.WD_BORDER_TOP).LineWidth = Config.WD_LINE_WIDTH_150PT
                tbl.Borders(Config.WD_BORDER_TOP).Color = Config.WD_COLOR_BLACK
                tbl.Borders(Config.WD_BORDER_BOTTOM).LineStyle = Config.WD_LINE_STYLE_SINGLE
                tbl.Borders(Config.WD_BORDER_BOTTOM).LineWidth = Config.WD_LINE_WIDTH_150PT
                tbl.Borders(Config.WD_BORDER_BOTTOM).Color = Config.WD_COLOR_BLACK

                if tbl.Rows.Count > 1:
                    header = tbl.Rows(1)
                    header.Borders(Config.WD_BORDER_BOTTOM).LineStyle = Config.WD_LINE_STYLE_SINGLE
                    header.Borders(Config.WD_BORDER_BOTTOM).LineWidth = Config.WD_LINE_WIDTH_075PT
                    header.Borders(Config.WD_BORDER_BOTTOM).Color = Config.WD_COLOR_BLACK

                # 对齐修正
                tbl.Range.ParagraphFormat.LeftIndent = 0
                tbl.Range.ParagraphFormat.FirstLineIndent = 0
                tbl.Range.ParagraphFormat.Alignment = Config.WD_ALIGN_PARAGRAPH_CENTER
                tbl.Rows.Alignment = Config.WD_ALIGN_ROW_CENTER
                tbl.AutoFitBehavior(Config.WD_AUTO_FIT_WINDOW)

    def _update_toc(self, doc):
        """刷新目录域"""
        if doc.TablesOfContents.Count > 0:
            print("   -> [TOC] 正在刷新目录页码...")
            for toc in doc.TablesOfContents:
                toc.Update()

    def build(self, component_keys, output_filename="Final_Output.docx", component_registry=None):
        """主入口：根据传入的 keys 列表组装文档（支持线程内调用）"""

        # 1. 初始化线程 COM 环境 (必须！)
        pythoncom.CoInitialize()

        new_doc = None
        try:
            print("=" * 50)
            print(f"开始构建文档: {output_filename}")
            print(f"包含组件: {component_keys}")
            print("=" * 50)

            registry = component_registry or COMPONENT_REGISTRY

            # 2. 准备文件列表
            files_to_merge = []
            for key in component_keys:
                if key not in registry:
                    print(f"[Warning] 未知组件 key: {key}，已跳过")
                    continue

                item = registry[key]

                if item["type"] == "static":
                    if os.path.exists(item["path"]):
                        files_to_merge.append(item["path"])
                    else:
                        print(f"[Error] 静态资源丢失: {item['path']}")

                elif item["type"] == "md":
                    # 动态转换 Markdown
                    print(f"   -> 转换 Markdown: {item['desc']}")
                    temp_docx_name = f"temp_{key}.docx"
                    temp_path = os.path.join(Config.TEMP_DIR, temp_docx_name)
                    result = self._pandoc_convert(item["path"], temp_path)
                    if result:
                        files_to_merge.append(result)

            if not files_to_merge:
                print("[Error] 没有文件可合并")
                return

            # 3. 启动 Word 进行合并
            print(f"[Merge] 正在启动 Word 进行合并...")
            self.word_app = None

            try:
                # === 健壮的 Word 启动逻辑 ===
                try:
                    self.word_app = win32.DispatchEx("Word.Application")
                except Exception as e:
                    # 捕获“服务器运行失败”，通常是因为此时屏幕上有个 Word 弹窗
                    if "服务器运行失败" in str(e) or "-2146959355" in str(e):
                        raise Exception(
                            "Word 启动失败。请检查：\n"
                            "1. 屏幕上是否有 Word 的安全弹窗或报错？请手动关闭它们。\n"
                            "2. 后台是否卡死了 WINWORD.EXE 进程？\n"
                            "3. 建议先打开一个空白 Word 文档，确保没有弹窗后再运行本工具。"
                        ) from e
                    raise

                # 稍等一下让 Word 完成初始化（减少偶发 COM 抖动）
                time.sleep(0.2)

                # 设置不可见，避免闪烁
                self.word_app.Visible = False

                # === 关键：尝试禁止弹窗 ===
                # 0 = wdAlertsNone
                self.word_app.DisplayAlerts = 0

                # 新建文档（基于 reference 模板）
                new_doc = self.word_app.Documents.Add(Template=Config.REF_DOC)
                if new_doc.Content.End > 1:
                    new_doc.Content.Delete()

                selection = self.word_app.Selection

                for i, file_path in enumerate(files_to_merge):
                    print(f"   -> 插入: {os.path.basename(file_path)}")
                    selection.InsertFile(FileName=file_path)

                    # 只有当不是最后一个文件时，才插入分页符
                    if i < len(files_to_merge) - 1:
                        selection.InsertBreak(Type=Config.WD_PAGE_BREAK)

                # 后处理
                self._update_toc(new_doc)
                self._process_styles(new_doc)

                # 保存
                abs_output_path = output_filename
                if not os.path.isabs(abs_output_path):
                    abs_output_path = os.path.join(Config.BASE_DIR, abs_output_path)

                new_doc.SaveAs(abs_output_path)
                new_doc.Close()
                new_doc = None
                print(f"\n[Success] 文档生成完毕: {abs_output_path}")

            except Exception as e:
                print(f"\n[Fatal Error] {e}")
                # 如果是 GUI 调用，这个 print 会被重定向到日志框，用户能看到提示
                if new_doc is not None:
                    try:
                        new_doc.Close(SaveChanges=False)
                    except Exception:
                        pass
                    new_doc = None

            finally:
                if self.word_app:
                    try:
                        self.word_app.Quit()
                    except Exception:
                        pass
                self.word_app = None

        finally:
            # 释放 COM 环境
            pythoncom.CoUninitialize()


# ================= 3. 用户调用层 (CLI 模拟) =================

def main():
    builder = DocumentBuilder()

    print("=" * 40)
    print("      SCAU 论文构建工具 CLI")
    print("=" * 40)
    print("请选择构建模式:")
    print("1. 完整毕业论文 (默认)")
    print("2. 自定义组装 (自由选择组件)")

    choice = input("\n请输入选项 [1]: ").strip()

    if choice == "2":
        # ================= 自定义模式逻辑 =================
        print("\n[可用组件列表]")

        # 获取所有注册的 key，并转为列表方便索引
        # 注意：Python 3.7+ 字典是有序的，这里会保持注册表定义的顺序
        keys = list(COMPONENT_REGISTRY.keys())

        for index, key in enumerate(keys):
            info = COMPONENT_REGISTRY[key]
            # 打印格式： 1. [封面] (cover)
            print(f"{index + 1}. [{info['desc']}] ({key})")

        print("\n提示：请输入组件对应的序号，用空格分隔。")
        print("例如输入 '1 6 7' 将按顺序组装：封面 -> 目录 -> 正文")

        user_input = input("请输入序列: ").strip()

        # 解析用户输入
        selected_components = []
        # 将逗号替换为空格，兼容两种分隔符，然后分割
        parts = user_input.replace(",", " ").split()

        for part in parts:
            if part.isdigit():
                idx = int(part) - 1  # 转为 0-based 索引
                if 0 <= idx < len(keys):
                    selected_key = keys[idx]
                    selected_components.append(selected_key)
                else:
                    print(f"[Warning] 序号 {part} 超出范围，已忽略")
            else:
                print(f"[Warning] '{part}' 不是有效数字，已忽略")

        if not selected_components:
            print("[Error] 未选择任何有效组件，程序退出。")
            return

        print(f"\n已选择: {selected_components}")
        output_name = "Custom_Output.docx"

    else:
        # ================= 默认模式 (完整论文) =================
        # 定义标准的论文顺序
        selected_components = [
            "cover",        # 封面
            "originality",  # 声明
            "abs_cn",       # 中文摘要
            "abs_en",       # 英文摘要
            "symbols",      # 符号表
            "toc",          # 目录
            "body",         # 正文
        ]
        output_name = "Final_Thesis.docx"

    # 执行构建
    builder.build(selected_components, output_name)


if __name__ == "__main__":
    main()
