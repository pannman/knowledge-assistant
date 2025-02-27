"""
RAG (Retrieval-Augmented Generation) エンジンモジュール
検索にAzure AI Search、生成にOpenAI APIを使用
"""

import os
from openai import OpenAI  # OpenAI APIを直接使用
import json
from datetime import datetime
from typing import List, Dict, Any, Tuple
from .azure_search import AzureSearchClient


class RAGEngine:
    """Retrieval-Augmented Generation (RAG)エンジン"""
    
    def __init__(self):
        """RAGエンジンの初期化"""
        # OpenAI API設定 - 直接OpenAIクライアントを使用
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")  # デフォルトはgpt-4o
        
        # Azure Search クライアント (検索のみに使用)
        self.search_client = AzureSearchClient()
    
    def generate_response(self, query: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        クエリに対する回答を生成
        
        Args:
            query: ユーザーからの質問
            
        Returns:
            (生成された回答, 参照ソースのリスト)
        """
        # 関連するFAQを検索 (Azure AI Searchを使用)
        search_results = self.search_client.search(query)
        
        # 検索結果からコンテキストを生成
        context_parts = []
        sources = []
        
        # PDFからの検索結果
        for i, result in enumerate(search_results["pdf"]):
            context_parts.append(f"PDF情報 {i+1}:\n質問: {result['question']}\n回答: {result['answer']}")
            
            # ソースリストに追加（重複を避ける）
            source_url = result["source_url"]
            if not any(s["url"] == source_url for s in sources):
                sources.append({
                    "type": "pdf",
                    "title": f"PDF文書 #{result.get('source_id', 'Unknown')}",
                    "url": source_url
                })
        
        # Slackからの検索結果
        for i, result in enumerate(search_results["slack"]):
            context_parts.append(f"Slack情報 {i+1}:\n質問: {result['question']}\n回答: {result['answer']}")
            
            # ソースリストに追加（重複を避ける）
            source_url = result["source_url"]
            if not any(s["url"] == source_url for s in sources):
                sources.append({
                    "type": "slack",
                    "title": f"Slackスレッド #{result.get('thread_id', 'Unknown')}",
                    "url": source_url
                })
        
        # コンテキストの組み立て
        context = "\n\n".join(context_parts)
        
        # ChainOfThoughtプロンプトを構築
        prompt = self._build_cot_prompt(query, context)
        
        # 回答の生成 - OpenAI API直接呼び出し
        try:
            response = self.client.chat.completions.create(
                model=self.model,  # "gpt-4o"などのOpenAIモデル名
                messages=[
                    {"role": "system", "content": """あなたは企業の社内知識アシスタントです。
                    社内マニュアルやSlackの会話から得られた情報を基に、正確で役立つ回答を提供してください。
                    与えられた情報だけに基づいて回答し、情報がない場合は正直に「わかりません」と答えてください。
                    回答は簡潔かつ丁寧な日本語で行い、専門用語があれば簡単な説明を加えてください。"""},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1200,
                temperature=0.3
            )
            
            generated_text = response.choices[0].message.content.strip()
            
            # Chain of Thoughtから実際の回答部分を抽出
            final_answer = self._extract_final_answer(generated_text)
            
            return final_answer, sources
        
        except Exception as e:
            print(f"Error generating response: {e}")
            return f"回答の生成中にエラーが発生しました: {str(e)}", []
    
    def _build_cot_prompt(self, query: str, context: str) -> str:
        """
        Chain of Thoughtプロンプトを構築
        
        Args:
            query: ユーザーからの質問
            context: 検索結果のコンテキスト
            
        Returns:
            構築されたプロンプト
        """
        return f"""以下の情報に基づいて質問に回答してください。

## 情報ソース:
{context}

## 質問:
{query}

## 指示:
1. まず与えられた情報を注意深く分析してください。
2. 質問に関連する情報を特定し、その重要性と信頼性を評価してください。
3. 情報源が複数ある場合は、それらを統合して一貫した回答を作成してください。
4. 情報が不足している場合は、その旨を正直に伝えてください。
5. 回答は明確、簡潔、かつ親切な日本語で作成してください。
6. 専門用語がある場合は、簡単な説明を加えてください。

## 思考プロセス:
質問を分析して、関連する情報源を確認します。各情報源の内容を検討し、回答を構築していきます。

"""
    
    def _extract_final_answer(self, generated_text: str) -> str:
        """
        Chain of Thought出力から最終回答部分を抽出
        
        Args:
            generated_text: LLMが生成したテキスト
            
        Returns:
            抽出された最終回答
        """
        # 「最終回答:」や「結論:」などの後の部分を抽出
        markers = ["最終回答:", "結論:", "回答:", "まとめると:", "以上を踏まえると:"]
        
        for marker in markers:
            if marker in generated_text:
                parts = generated_text.split(marker)
                if len(parts) > 1:
                    return parts[1].strip()
        
        # マーカーが見つからない場合は、思考プロセスを除去して返す
        if "思考プロセス:" in generated_text:
            parts = generated_text.split("思考プロセス:")
            if len(parts) > 1 and "情報源" in parts[1]:
                # 情報源の解析後の部分を抽出
                analysis_parts = parts[1].split("\n\n", 1)
                if len(analysis_parts) > 1:
                    return analysis_parts[1].strip()
        
        # それでも見つからない場合は、原文をそのまま返す
        return generated_text