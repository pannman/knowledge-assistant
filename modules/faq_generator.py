"""
FAQ生成モジュール
Chain of Thought、Few-shotとStructured Outputを活用した改良版FAQ生成システム
OpenAI APIを直接使用するバージョン
"""

import os
from openai import OpenAI  # OpenAI APIを直接使用
from typing import List, Dict, Any, Tuple
import tiktoken  # トークンカウント用
from tqdm import tqdm  # プログレスバー表示用

from .text_processors import PDFTextProcessor, SlackConversationProcessor
from .prompt_templates import PromptBuilder
from .postprocessors import FAQPostProcessor, LLMOutputParser


class FAQGenerator:
    """LLMを使用してFAQを生成するクラス（改良版）"""
    
    def __init__(self):
        """FAQ生成器の初期化"""
        # OpenAI API直接使用
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        self.model = "gpt-4"
        
        # テンプレートビルダーの初期化
        self.prompt_builder = PromptBuilder()
        
        # トークンカウンター初期化
        self.encoding = tiktoken.encoding_for_model(self.model)
        self.total_tokens_used = 0
    
    def count_tokens(self, text: str) -> int:
        """テキストのトークン数をカウント"""
        return len(self.encoding.encode(text))
    
    def generate_summary(self, text: str) -> str:
        """テキストの要約を生成"""
        try:
            print("\n📝 要約を生成中...")
            input_tokens = self.count_tokens(text)
            print(f"入力テキストのトークン数: {input_tokens}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "あなたは与えられたテキストを簡潔に要約するエキスパートです。"},
                    {"role": "user", "content": f"以下のテキストを200文字以内で要約してください：\n\n{text}"}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            output = response.choices[0].message.content.strip()
            output_tokens = self.count_tokens(output)
            total_tokens = response.usage.total_tokens
            self.total_tokens_used += total_tokens
            
            print(f"生成された要約のトークン数: {output_tokens}")
            print(f"このリクエストの合計トークン使用量: {total_tokens}")
            print(f"累計トークン使用量: {self.total_tokens_used}")
            
            return output
        
        except Exception as e:
            print(f"❌ 要約生成エラー: {e}")
            return "要約を生成できませんでした。"
    
    def generate_faqs_from_text(
        self, 
        text: str, 
        source_type: str, 
        source_id: str, 
        source_url: str, 
        context: str = ""
    ) -> List[Dict[str, Any]]:
        """テキストからFAQを生成"""
        try:
            print("\n🔄 FAQ生成プロセスを開始...")
            
            # 1. ソースタイプに応じたテキスト前処理
            print("1️⃣ テキストを前処理中...")
            if source_type == "pdf":
                processed_result = PDFTextProcessor.process(text)
                processed_text = processed_result["enhanced_text"]
            elif source_type == "slack":
                processed_result = SlackConversationProcessor.process(text)
                processed_text = processed_result["enhanced_text"]
            else:
                processed_text = text
            
            # 2. ソースタイプに応じたプロンプト作成
            print("2️⃣ プロンプトを生成中...")
            if source_type == "pdf":
                prompt = self.prompt_builder.get_pdf_faq_prompt(processed_text, context)
            elif source_type == "slack":
                prompt = self.prompt_builder.get_slack_faq_prompt(processed_text, context)
            else:
                prompt = self.prompt_builder.get_generic_faq_prompt(processed_text, context)
            
            input_tokens = self.count_tokens(prompt)
            print(f"プロンプトのトークン数: {input_tokens}")
            
            # 3. LLMを使用してFAQを生成 - OpenAI API直接使用
            print("3️⃣ LLMでFAQを生成中...")
            response = self.client.chat.completions.create(
                model=self.model,  # "gpt-4o"などのOpenAIモデル名
                messages=[
                    {"role": "system", "content": "あなたは高品質なFAQ生成AIアシスタントです。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=3000,  # Chain of Thoughtのため増量
                temperature=0.5
            )
            
            llm_response = response.choices[0].message.content.strip()
            output_tokens = self.count_tokens(llm_response)
            total_tokens = response.usage.total_tokens
            self.total_tokens_used += total_tokens
            
            print(f"生成されたFAQのトークン数: {output_tokens}")
            print(f"このリクエストの合計トークン使用量: {total_tokens}")
            print(f"累計トークン使用量: {self.total_tokens_used}")
            
            # 4. LLM出力を解析
            print("4️⃣ LLM出力を解析中...")
            faqs = LLMOutputParser.parse_faq_response(llm_response)
            
            # FAQの解析と表示を追加
            print("\n📋 生成されたFAQ一覧:")
            for i, faq in enumerate(faqs, 1):
                print(f"\n----- FAQ #{i} -----")
                print(f"Q: {faq.get('question', '')}")
                print(f"A: {faq.get('answer', '')}")
                print("-" * 50)
            
            # メタデータ追加
            print("\n5️⃣ メタデータを追加中...")
            result = []
            for faq in faqs:
                result.append({
                    "question": faq.get("question", ""),
                    "answer": faq.get("answer", ""),
                    "source_type": source_type,
                    "source_id": source_id,
                    "source_url": source_url
                })
            
            # FAQ後処理
            print("6️⃣ FAQ後処理を実行中...")
            processed_faqs = FAQPostProcessor.process(result, source_type, source_url)
            
            # 処理結果のサマリー表示
            print(f"\n✅ FAQ生成完了！")
            print(f"• 生成されたFAQ数: {len(processed_faqs)}")
            print(f"• 累計トークン使用量: {self.total_tokens_used}")
            
            return processed_faqs
        
        except Exception as e:
            print(f"❌ FAQ生成エラー: {e}")
            return []