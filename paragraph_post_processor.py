import os
import re
from google import genai
from google.genai import types
import time
import shutil

def safely_rename_files(directory, prefix="paragraph_"):
    """
    安全地重新命名目錄中所有帶有指定前綴的檔案，以確保順序連續
    
    Args:
        directory: 檔案所在目錄
        prefix: 檔案名稱前綴
    """
    # 獲取目錄中的所有檔案
    files = [f for f in os.listdir(directory) if f.startswith(prefix) and f.endswith('.txt')]
    
    # 按照數字排序
    files.sort(key=lambda x: int(x.split('_')[1].split('.')[0]))
    
    # 先將所有檔案重命名為臨時名稱，避免衝突
    temp_files = []
    for i, file_name in enumerate(files):
        old_path = os.path.join(directory, file_name)
        temp_name = f"{prefix}temp_{i+1}.txt"
        temp_path = os.path.join(directory, temp_name)
        os.rename(old_path, temp_path)
        temp_files.append(temp_name)
    
    # 再將臨時檔案按照正確順序重命名
    for i, temp_name in enumerate(temp_files):
        temp_path = os.path.join(directory, temp_name)
        new_name = f"{prefix}{i+1}.txt"
        new_path = os.path.join(directory, new_name)
        os.rename(temp_path, new_path)
    
    # 返回更新後的檔案名列表
    return [f"{prefix}{i+1}.txt" for i in range(len(files))]

def check_paragraph_continuity(paragraph1, paragraph2, api_key):
    """檢查兩個段落連接起來是否合理"""
    # 設置模型
    client = genai.Client(api_key=api_key)
    
    # 準備提示
    prompt = """請判斷以下兩個段落是否是連續的內容，應該合併為同一段落。

段落1:
{paragraph1}

段落2:
{paragraph2}

判斷標準:
1. 段落1是否未完成的句子，段落2是否是段落1的延續
2. 段落1和段落2是否討論同一主題，且邏輯上緊密相連
3. 兩段文字合併後是否更通順、更完整

請只回覆 "是" 或 "否"，不要解釋原因。
"""
    
    # 填入段落
    filled_prompt = prompt.format(paragraph1=paragraph1, paragraph2=paragraph2)
    
    # 使用Gemini分析
    response = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents=[filled_prompt],
        config=types.GenerateContentConfig(
            max_output_tokens=10,
            temperature=0.1
        )
    )
    
    # 等待一下以避免API限制
    time.sleep(2)
    
    # 獲取回答並判斷
    answer = response.text.strip().lower()
    return "是" in answer

def merge_paragraph_files(file1_path, file2_path, output_path):
    """合併兩個段落文件"""
    with open(file1_path, 'r', encoding='utf-8') as f1:
        content1 = f1.read()
    
    with open(file2_path, 'r', encoding='utf-8') as f2:
        content2 = f2.read()
    
    # 合併內容
    merged_content = content1.strip() + " " + content2.strip()
    
    # 寫入新文件
    with open(output_path, 'w', encoding='utf-8') as f_out:
        f_out.write(merged_content)
    
    return merged_content

def is_bullet_or_numbered_list(text):
    """檢查文本是否以•或數字+點開頭"""
    # 去除可能的空白
    text = text.strip()
    
    # 檢查是否以•開頭
    if text.startswith('•'):
        return True
    
    # 檢查是否以數字+點開頭，允許項目符號前有空格
    number_pattern = r'^\s*\d+\.'
    if re.match(number_pattern, text):
        return True
    
    return False

def get_next_number(text):
    """從文本中提取第一個數字（用於判斷序號）"""
    number_match = re.match(r'^\s*(\d+)\.', text)
    if number_match:
        return int(number_match.group(1))
    return None

def post_process_paragraphs(base_dir, page_numbers, api_key):
    """對分割後的段落文件進行二次處理"""
    print("開始段落後處理...")
    
    # 1. 檢查每頁的最後一個段落與下一頁的第一個段落是否應連接
    for i in range(len(page_numbers) - 1):
        current_page = page_numbers[i]
        next_page = page_numbers[i + 1]
        
        # 獲取當前頁目錄
        current_page_dir = os.path.join(base_dir, str(current_page))
        next_page_dir = os.path.join(base_dir, str(next_page))
        
        # 確保目錄存在
        if not os.path.exists(current_page_dir) or not os.path.exists(next_page_dir):
            continue
        
        # 獲取當前頁的段落文件列表
        current_page_files = [f for f in os.listdir(current_page_dir) if f.startswith('paragraph_')]
        if not current_page_files:
            continue
        
        # 排序以確保獲取最後一個段落
        current_page_files.sort(key=lambda x: int(x.split('_')[1].split('.')[0]))
        last_paragraph_file = os.path.join(current_page_dir, current_page_files[-1])
        
        # 獲取下一頁的段落文件列表
        next_page_files = [f for f in os.listdir(next_page_dir) if f.startswith('paragraph_')]
        if not next_page_files:
            continue
        
        # 排序以確保獲取第一個段落
        next_page_files.sort(key=lambda x: int(x.split('_')[1].split('.')[0]))
        first_paragraph_file = os.path.join(next_page_dir, next_page_files[0])
        
        # 讀取段落內容
        with open(last_paragraph_file, 'r', encoding='utf-8') as f:
            last_paragraph = f.read()
        
        with open(first_paragraph_file, 'r', encoding='utf-8') as f:
            first_paragraph = f.read()
        
        # 檢查是否應該合併
        if check_paragraph_continuity(last_paragraph, first_paragraph, api_key):
            print(f"合併頁面 {current_page} 的最後段落與頁面 {next_page} 的第一段落")
            
            # 創建合併的新文件
            merged_file = os.path.join(current_page_dir, f'paragraph_{int(current_page_files[-1].split("_")[1].split(".")[0])}_merged.txt')
            merge_paragraph_files(last_paragraph_file, first_paragraph_file, merged_file)
            
            # 刪除原始文件
            os.remove(last_paragraph_file)
            os.remove(first_paragraph_file)
            
            # 重命名合併後的文件
            os.rename(merged_file, last_paragraph_file)
            
            # 重新命名下一頁的所有檔案，確保順序連續
            safely_rename_files(next_page_dir)
    
    # 2. 處理冒號結尾的段落和列表項
    for page_idx, page in enumerate(page_numbers):
        page_dir = os.path.join(base_dir, str(page))
        
        # 確保目錄存在
        if not os.path.exists(page_dir):
            continue
        
        # 處理該頁的所有段落
        i = 0
        while True:
            # 重新獲取所有段落文件並排序
            paragraph_files = [f for f in os.listdir(page_dir) if f.startswith('paragraph_')]
            if not paragraph_files:
                break
                
            paragraph_files.sort(key=lambda x: int(x.split('_')[1].split('.')[0]))
            
            # 檢查是否已經處理完所有段落
            if i >= len(paragraph_files):
                break
                
            current_file = os.path.join(page_dir, paragraph_files[i])
            
            # 讀取當前段落
            try:
                with open(current_file, 'r', encoding='utf-8') as f:
                    current_text = f.read().strip()
            except FileNotFoundError:
                # 文件可能在之前的操作中被刪除，重新整理文件列表
                i = 0
                continue
            
            # 檢查是否以冒號結尾（包括全形和半形冒號）
            if current_text.rstrip().endswith(':') or current_text.rstrip().endswith('：'):
                next_text = None
                next_file = None
                next_page_dir = None
                is_next_page = False
                
                # 檢查是否有當前頁的下一個段落
                if i + 1 < len(paragraph_files):
                    next_file = os.path.join(page_dir, paragraph_files[i + 1])
                    try:
                        with open(next_file, 'r', encoding='utf-8') as f:
                            next_text = f.read().strip()
                    except FileNotFoundError:
                        # 重新獲取文件列表
                        break
                
                # 如果是該頁的最後一個段落，需要檢查下一頁的第一個段落
                elif page_idx + 1 < len(page_numbers):
                    next_page = page_numbers[page_idx + 1]
                    next_page_dir = os.path.join(base_dir, str(next_page))
                    
                    # 確保下一頁目錄存在
                    if os.path.exists(next_page_dir):
                        next_page_files = [f for f in os.listdir(next_page_dir) if f.startswith('paragraph_')]
                        
                        if next_page_files:
                            next_page_files.sort(key=lambda x: int(x.split('_')[1].split('.')[0]))
                            next_file = os.path.join(next_page_dir, next_page_files[0])
                            
                            try:
                                with open(next_file, 'r', encoding='utf-8') as f:
                                    next_text = f.read().strip()
                                    is_next_page = True
                            except FileNotFoundError:
                                # 重新獲取文件列表
                                break
                
                # 如果找到了下一個段落文本
                if next_text is not None:
                    # 檢查下一段是否為列表項
                    if is_bullet_or_numbered_list(next_text):
                        print(f"發現冒號結尾段落後跟隨列表項: {current_file}" + (" (下一頁)" if is_next_page else ""))
                        
                        # 合併段落
                        merged_content = current_text + "\n" + next_text
                        with open(current_file, 'w', encoding='utf-8') as f:
                            f.write(merged_content)
                        
                        # 刪除合併後的文件
                        os.remove(next_file)
                        
                        # 重新命名所有檔案
                        if is_next_page and next_page_dir:
                            safely_rename_files(next_page_dir)
                        else:
                            safely_rename_files(page_dir)
                            
                        # 檢查是否繼續合併列表項
                        if not is_next_page:
                            # 重新獲取更新後的文件列表
                            paragraph_files = safely_rename_files(page_dir)
                            
                            # 檢查是否還有更多的列表項
                            continue_merging = True
                            current_number = get_next_number(next_text)
                            
                            while continue_merging and i + 1 < len(paragraph_files):
                                next_file_name = paragraph_files[i + 1]
                                next_file = os.path.join(page_dir, next_file_name)
                                
                                try:
                                    with open(next_file, 'r', encoding='utf-8') as f:
                                        next_text = f.read().strip()
                                except FileNotFoundError:
                                    break
                                
                                # 檢查是否是連續的列表項
                                is_bullet = next_text.startswith('•')
                                next_number = get_next_number(next_text)
                                
                                if (is_bullet and '•' in merged_content) or \
                                   (current_number is not None and next_number is not None and next_number == current_number + 1):
                                    # 繼續合併
                                    with open(current_file, 'r', encoding='utf-8') as f:
                                        merged_content = f.read() + "\n" + next_text
                                    
                                    with open(current_file, 'w', encoding='utf-8') as f:
                                        f.write(merged_content)
                                    
                                    # 更新當前數字
                                    current_number = next_number
                                    
                                    # 刪除合併後的文件
                                    os.remove(next_file)
                                    
                                    # 重新命名檔案
                                    safely_rename_files(page_dir)
                                    
                                    # 更新檔案列表
                                    paragraph_files = [f for f in os.listdir(page_dir) if f.startswith('paragraph_')]
                                    paragraph_files.sort(key=lambda x: int(x.split('_')[1].split('.')[0]))
                                else:
                                    continue_merging = False
                    else:
                        # 冒號結尾但下一段不是列表項，刪除該段
                        print(f"刪除冒號結尾但後面不是列表項的段落: {current_file}")
                        os.remove(current_file)
                        
                        # 重新命名剩餘檔案
                        if is_next_page and next_page_dir:
                            # 不需要重命名下一頁的檔案，只刪除了當前頁的檔案
                            safely_rename_files(page_dir)
                        else:
                            safely_rename_files(page_dir)
                        
                        # 重設索引以從頭開始檢查
                        i = 0
                        continue
                else:
                    # 冒號結尾但沒有下一段（甚至下一頁），刪除該段
                    print(f"刪除冒號結尾且找不到後續段落的段落: {current_file}")
                    os.remove(current_file)
                    
                    # 重新命名剩餘檔案
                    safely_rename_files(page_dir)
                    
                    # 重設索引以從頭開始檢查
                    i = 0
                    continue
            
            # 進入下一個段落
            i += 1
    
    print("段落後處理完成")


# 使用範例
if __name__ == "__main__":
    # 測試代碼
    base_dir = "output_paragraphs2"
    page_list = [i for i in range(80)]
    page_numbers = [4, 5, 6, 7]  # 範例頁碼
    api_key = "api_key"
    post_process_paragraphs(base_dir, page_list, api_key)