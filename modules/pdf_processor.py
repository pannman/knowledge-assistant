import os
import PyPDF2
import tempfile
from typing import List, Dict, Any

class PDFProcessor:
    """PDFファイルの処理クラス"""
    
    def __init__(self):
        """PDFプロセッサの初期化"""
        pass
    
    def extract_text(self, pdf_path: str) -> List[Dict[str, Any]]:
        """PDFからテキストを抽出し、チャンク単位で返す"""
        chunks = []
        
        try:
            with open(pdf_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                num_pages = len(reader.pages)
                
                # ページごとにテキストを抽出
                for page_num in range(num_pages):
                    page = reader.pages[page_num]
                    text = page.extract_text()
                    
                    if text.strip():
                        # チャンクに分割（ここではページ単位）
                        chunks.append({
                            "page_num": page_num + 1,
                            "text": text,
                            "char_count": len(text)
                        })
            
            # より細かいチャンクに分割
            processed_chunks = self._split_into_chunks(chunks)
            return processed_chunks
        
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return []
    
    def _split_into_chunks(self, page_chunks: List[Dict[str, Any]], max_chunk_size: int = 1000) -> List[Dict[str, Any]]:
        """テキストをより細かいチャンクに分割"""
        result_chunks = []
        
        for page_chunk in page_chunks:
            text = page_chunk["text"]
            page_num = page_chunk["page_num"]
            
            # テキストが最大チャンクサイズを超える場合に分割
            if len(text) <= max_chunk_size:
                result_chunks.append({
                    "page_num": page_num,
                    "text": text,
                    "char_count": len(text)
                })
            else:
                # 段落で分割を試みる
                paragraphs = text.split('\n\n')
                current_chunk = ""
                
                for para in paragraphs:
                    if len(current_chunk) + len(para) + 2 <= max_chunk_size:
                        if current_chunk:
                            current_chunk += "\n\n" + para
                        else:
                            current_chunk = para
                    else:
                        # 現在のチャンクを保存し、新しいチャンクを開始
                        if current_chunk:
                            result_chunks.append({
                                "page_num": page_num,
                                "text": current_chunk,
                                "char_count": len(current_chunk)
                            })
                        
                        # 段落自体が最大サイズを超える場合は、さらに分割
                        if len(para) > max_chunk_size:
                            words = para.split(' ')
                            current_chunk = ""
                            
                            for word in words:
                                if len(current_chunk) + len(word) + 1 <= max_chunk_size:
                                    if current_chunk:
                                        current_chunk += " " + word
                                    else:
                                        current_chunk = word
                                else:
                                    result_chunks.append({
                                        "page_num": page_num,
                                        "text": current_chunk,
                                        "char_count": len(current_chunk)
                                    })
                                    current_chunk = word
                        else:
                            current_chunk = para
                
                # 残りのチャンクを保存
                if current_chunk:
                    result_chunks.append({
                        "page_num": page_num,
                        "text": current_chunk,
                        "char_count": len(current_chunk)
                    })
        
        return result_chunks

    def get_document_metadata(self, pdf_path: str) -> Dict[str, Any]:
        """PDFのメタデータを取得"""
        try:
            with open(pdf_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                info = reader.metadata
                
                if info:
                    return {
                        "title": info.get("/Title", os.path.basename(pdf_path)),
                        "author": info.get("/Author", "Unknown"),
                        "subject": info.get("/Subject", ""),
                        "keywords": info.get("/Keywords", ""),
                        "creator": info.get("/Creator", ""),
                        "producer": info.get("/Producer", ""),
                        "page_count": len(reader.pages)
                    }
                else:
                    return {
                        "title": os.path.basename(pdf_path),
                        "page_count": len(reader.pages)
                    }
        
        except Exception as e:
            print(f"Error getting PDF metadata: {e}")
            return {
                "title": os.path.basename(pdf_path),
                "error": str(e)
            }