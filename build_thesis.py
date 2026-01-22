import os
import subprocess
import win32com.client as win32

# ================= 配置路径 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
MD_DIR = os.path.join(BASE_DIR, "md")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

# 输入文件 (Markdown)
MD_FILES = {
    "abs_cn": os.path.join(MD_DIR, "abstract_cn.md"),
    "abs_en": os.path.join(MD_DIR, "abstract_en.md"),
    "body":   os.path.join(MD_DIR, "body.md")
}

# 静态素材 (Word)
STATIC_FILES = {
    "cover":       os.path.join(ASSETS_DIR, "cover.docx"),
    "originality": os.path.join(ASSETS_DIR, "originality_declaration.docx"),
    "symbols":     os.path.join(ASSETS_DIR, "symbols.docx"),
    "toc":         os.path.join(ASSETS_DIR, "toc.docx")
}

# 样式基准
REF_DOC = os.path.join(BASE_DIR, "reference.docx")
# 最终输出
OUTPUT_DOCX = os.path.join(BASE_DIR, "Final_Thesis.docx")

# 确保临时文件夹存在
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# ================= Word 常量 =================
wdPageBreak = 7
wdBorderTop = -1
wdBorderBottom = -3
wdLineStyleSingle = 1
wdLineWidth150pt = 12    # 1.5磅
wdLineWidth075pt = 6     # 0.75磅
wdColorBlack = 0         # 黑色
wdAlignParagraphCenter = 1
wdAlignRowCenter = 1
wdAutoFitWindow = 2

def pandoc_convert(input_md, output_docx):
    """将单个MD转换为临时Docx"""
    if not os.path.exists(input_md):
        print(f"[Error] 找不到文件: {input_md}")
        return None
    
    # 依然使用 reference-doc 参数，确保生成的临时文件样式正确
    cmd = f'pandoc "{input_md}" --reference-doc="{REF_DOC}" -o "{output_docx}"'
    try:
        subprocess.run(cmd, shell=True, check=True)
        return output_docx
    except subprocess.CalledProcessError:
        print(f"[Error] 转换失败: {input_md}")
        return None

def merge_documents(doc_list):
    """核心：拼装文档"""
    print("[2/3] 正在组装文档...")
    word = win32.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = False
    
    try:
        # [关键修改] 使用 REF_DOC 作为模板创建新文档
        # 这确保了主文档拥有正确的 Heading 1, Normal 等内置样式定义
        new_doc = word.Documents.Add(Template=REF_DOC)
        
        # 如果模板里有内容（例如占位符），先清空
        if new_doc.Content.End > 1: # 文档不为空
            new_doc.Content.Delete()

        selection = word.Selection
        
        for i, doc_path in enumerate(doc_list):
            if not doc_path or not os.path.exists(doc_path):
                print(f"   -> [Warning] 文件不存在，跳过: {doc_path}")
                continue
                
            print(f"   -> 正在插入: {os.path.basename(doc_path)}")
            selection.InsertFile(FileName=doc_path)
            
            # 如果不是最后一个文件，插入分页符
            if i < len(doc_list) - 1:
                selection.InsertBreak(Type=wdPageBreak)
        
        new_doc.SaveAs(OUTPUT_DOCX)
        new_doc.Close()
        print("   -> 组装完成。")
        return True
    except Exception as e:
        print(f"   -> [Error] 组装过程出错: {e}")
        if 'new_doc' in locals():
            new_doc.Close(SaveChanges=False)
        return False
    finally:
        # 保持 Word 进程开启给下一步用，或者在这里 Quit 也可以
        # 建议这里不 Quit，因为下一步马上又要打开
        pass

def post_process_styles():
    """后处理：三线表修复 & 图片居中 & 格式矫正"""
    print("[3/3] 正在精修文档样式（表格 & 图片）...")
    
    word = win32.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = False 

    try:
        doc = word.Documents.Open(OUTPUT_DOCX)
        
        # ==========================================
        # Part A: 图片处理 (新增部分)
        # ==========================================
        # InlineShapes 代表嵌入式图片（Pandoc默认生成的都是这种）
        if doc.InlineShapes.Count > 0:
            print(f"   -> 检测到 {doc.InlineShapes.Count} 张图片，正在执行居中...")
            for shape in doc.InlineShapes:
                # 将图片所在段落设置为居中 (1 = wdAlignParagraphCenter)
                shape.Range.ParagraphFormat.Alignment = wdAlignParagraphCenter
                # 清除首行缩进（防止图片居中但偏右）
                shape.Range.ParagraphFormat.FirstLineIndent = 0
                shape.Range.ParagraphFormat.CharacterUnitFirstLineIndent = 0
        
        # ==========================================
        # Part B: 表格处理 (原有逻辑)
        # ==========================================
        if doc.Tables.Count > 0:
            print(f"   -> 检测到 {doc.Tables.Count} 个表格，正在处理...")
            for tbl in doc.Tables:
                # 1. 边框设置
                tbl.Borders.Enable = False
                tbl.Borders(wdBorderTop).LineStyle = wdLineStyleSingle
                tbl.Borders(wdBorderTop).LineWidth = wdLineWidth150pt
                tbl.Borders(wdBorderTop).Color = wdColorBlack
                tbl.Borders(wdBorderBottom).LineStyle = wdLineStyleSingle
                tbl.Borders(wdBorderBottom).LineWidth = wdLineWidth150pt
                tbl.Borders(wdBorderBottom).Color = wdColorBlack
                
                if tbl.Rows.Count > 1:
                    header_row = tbl.Rows(1)
                    header_row.Borders(wdBorderBottom).LineStyle = wdLineStyleSingle
                    header_row.Borders(wdBorderBottom).LineWidth = wdLineWidth075pt
                    header_row.Borders(wdBorderBottom).Color = wdColorBlack

                # 2. 格式矫正
                tbl.Range.ParagraphFormat.LeftIndent = 0
                tbl.Range.ParagraphFormat.FirstLineIndent = 0
                tbl.Range.ParagraphFormat.CharacterUnitFirstLineIndent = 0
                tbl.Range.ParagraphFormat.Alignment = wdAlignParagraphCenter
                tbl.Rows.Alignment = wdAlignRowCenter 
                tbl.AutoFitBehavior(wdAutoFitWindow)

        doc.Save()
        print("   -> 样式精修完成。")
        
    except Exception as e:
        print(f"   -> [Error] 样式处理出错: {e}")
    finally:
        if 'doc' in locals():
            doc.Close()
        word.Quit()


def update_toc(doc_path):
    print("   -> [Post-Process] 正在刷新目录页码...")
    word = win32.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = False
    try:
        doc = word.Documents.Open(doc_path)
        # 遍历所有目录域并更新
        if doc.TablesOfContents.Count > 0:
            for toc in doc.TablesOfContents:
                toc.Update()
        doc.Save()
    except Exception as e:
        print(f"   -> [Warning] 目录更新失败: {e}")
    finally:
        if 'doc' in locals(): doc.Close()
        word.Quit()

def main():
    print("="*50)
    print("      SCAU 论文拼装流水线")
    print("="*50)

    # 1. 转换 Markdown 部分
    print("[1/3] 转换 Markdown 片段...")
    temp_abs_cn = pandoc_convert(MD_FILES["abs_cn"], os.path.join(TEMP_DIR, "t_abs_cn.docx"))
    temp_abs_en = pandoc_convert(MD_FILES["abs_en"], os.path.join(TEMP_DIR, "t_abs_en.docx"))
    temp_body   = pandoc_convert(MD_FILES["body"],   os.path.join(TEMP_DIR, "t_body.docx"))

    # 定义拼装顺序
    # 2. 修改拼装顺序 (根据 SCAU 标准调整顺序)
    # 通常顺序：封面 -> 声明 -> 中文摘要 -> 英文摘要 -> 目录 -> 符号表 -> 正文
    assembly_line = [
        STATIC_FILES["cover"],
        STATIC_FILES["originality"],
        temp_abs_cn,
        temp_abs_en,
        STATIC_FILES["symbols"],
        STATIC_FILES["toc"],  # <--- 插入目录组件
        temp_body
    ]

    # 2. 执行拼装
    if merge_documents(assembly_line):
        # 3. 后处理：必须更新目录，否则显示“未找到目录项”
        update_toc(OUTPUT_DOCX)
        post_process_styles() # 原有的表格处理
        print(f"\n[Success] 论文生成完毕: {OUTPUT_DOCX}")
    else:
        print("\n[Failed] 流程中止")

if __name__ == "__main__":
    main()