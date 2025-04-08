import fitz  # PyMuPDF
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
import base64
from PIL import Image
import io
import time

api_key = "api_key"

def extract_page_as_text(pdf_path, page_number):
    """提取 PDF 特定頁面的文本，保留段落和基本排版"""
    doc = fitz.open(pdf_path)
    
    if page_number < 0 or page_number >= len(doc):
        raise ValueError(f"頁面編號無效。PDF 僅有 {len(doc)} 頁")
    
    page = doc[page_number]
    text = page.get_text()
    doc.close()
    
    return text

def extract_page_as_image(pdf_path, page_number):
    """將 PDF 頁面轉換為圖像"""
    doc = fitz.open(pdf_path)
    
    if page_number < 0 or page_number >= len(doc):
        raise ValueError(f"頁面編號無效。PDF 僅有 {len(doc)} 頁")
    
    page = doc[page_number]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x放大以獲得更好的圖像品質
    
    img_bytes = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_bytes))
    
    doc.close()
    return img

def analyze_content_with_gemini(pdf_path, page_number, use_image=True):
    """使用 Gemini 分析 PDF 頁面內容並進行段落分割"""
    
    # 設置模型
    client = genai.Client(api_key=api_key)
    
    # 準備提示
    prompt = """請分析這個 PDF 頁面的內容，但僅關注說明型文章的部分。

    請遵循以下篩選規則：
    1. 僅提取連續完整的說明性文字段落（如背景介紹、方法說明、分析討論、條列式說明等）
    2. 忽略以下內容類型：
    - 數學公式和推導過程
    - 目錄、索引和參考文獻
    - 表格內容和表格說明
    - 圖表標籤和圖表說明
    - 代碼片段
    - 作者資訊和單純的標題

    對於符合條件的說明型文字段落：
    1. 將每個段落標記為 "[[段落N]]"（N 是段落編號）
    2. 確保同個段落的內容被分割在同個段落
    3. 如果段落中嵌入了短公式，但段落主體是說明文字，則保留整個段落

    如果頁面上沒有符合條件的說明型文字，請回覆 "[[無符合條件的內容]]"
    """
    
    if use_image:
        # 使用圖像方式（保留完整排版和視覺元素）
        img = extract_page_as_image(pdf_path, page_number)
        
        # 使用 Gemini 的多模態功能分析內容
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=[img],
            config = types.GenerateContentConfig(
                max_output_tokens=10000,
                temperature=0.5,
                system_instruction=prompt
                )
            )
        
    else:
        # 使用文本方式（可能丟失一些排版信息）
        text = extract_page_as_text(pdf_path, page_number)
        
        # 添加文本到提示中
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=[text],
            config = types.GenerateContentConfig(
                max_output_tokens=10000,
                temperature=0.5,
                system_instruction=prompt
                )
            )
    time.sleep(2)
    return response.text

def filter_short_paragraphs(paragraphs, min_length=10):
    """過濾掉長度過短的段落
    
    Args:
        paragraphs: 段落列表
        min_length: 最小字符數 (預設為10個字符)
        
    Returns:
        過濾後的段落列表
    """
    filtered_paragraphs = []
    
    for i, paragraph in enumerate(paragraphs):
        # 移除空白字符後計算長度
        trimmed = paragraph.strip()
        if len(trimmed) >= min_length:
            filtered_paragraphs.append(paragraph)
        else:
            print(f"已過濾段落 {i+1} (長度: {len(trimmed)}): '{trimmed}'")
    
    return filtered_paragraphs

def extract_filtered_paragraphs(analysis_result):
    """從分析結果中提取篩選後的段落"""
    import re
    
    # 檢查是否有符合條件的內容
    if "[[無符合條件的內容]]" in analysis_result:
        return []
    
    # 提取段落
    paragraphs = re.split(r'\[\[段落\d+\]\]', analysis_result)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    
    return paragraphs

def save_paragraphs_to_files(analysis_result, output_dir="output_paragraphs", min_length=30):
    """將 Gemini 分析後的段落保存為單獨的文本文件"""
    # 創建輸出目錄
    os.makedirs(output_dir, exist_ok=True)
    
    paragraphs = extract_filtered_paragraphs(analysis_result)
    
    filtered_paragraphs = filter_short_paragraphs(paragraphs, min_length)
    
    print(f"總段落數: {len(paragraphs)}, 過濾後段落數: {len(filtered_paragraphs)}")
    
    # 保存每個段落
    for i, paragraph in enumerate(filtered_paragraphs):
        with open(f"{output_dir}/paragraph_{i+1}.txt", "w", encoding="utf-8") as f:
            f.write(paragraph)
    
    return len(filtered_paragraphs)

# 主函數
def process_pdf_page(pdf_path, page_number, use_image=True, min_length=30):
    """處理 PDF 頁面並使用 Gemini 進行分析"""
    print(f"正在處理 PDF: {pdf_path}, 頁面: {page_number}")
    
    # 分析內容
    analysis = analyze_content_with_gemini(pdf_path, page_number, use_image)
    
    # 保存段落
    num_paragraphs = save_paragraphs_to_files(analysis, min_length=min_length, output_dir=f"output_paragraphs/{page_number}")
    
    print(f"分析完成，共識別出 {num_paragraphs} 個段落")
    print(f"段落已保存到 output_paragraphs 目錄")
    
    return analysis

# 使用範例
if __name__ == "__main__":
    pdf_path = "./pdf_file/中央論文1.pdf"  # 替換為你的PDF路徑
    start_page_number = 0  # PDF頁碼（從0開始）
    pdf_length = len(fitz.open(pdf_path))
    for page_number in range(start_page_number, pdf_length, 1):
        # 執行分析（使用圖像模式以保留更多排版信息）
        analysis_result = process_pdf_page(pdf_path, page_number, use_image=True, min_length=30)
        
        # 顯示分析結果
        print(f"\n第{page_number}頁分析結果預覽：")
        print(analysis_result[:500] + "..." if len(analysis_result) > 500 else analysis_result)