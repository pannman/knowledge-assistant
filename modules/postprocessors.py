"""
生成結果の後処理モジュール
FAQの品質向上と一貫性を確保するためのユーティリティ
"""

import re
from typing import List, Dict, Any, Tuple, Set


class FAQPostProcessor:
    """FAQ生成結果の後処理を行うクラス"""
    
    @staticmethod
    def process(faqs: List[Dict[str, Any]], source_type: str, source_url: str = None) -> List[Dict[str, Any]]:
        """
        生成されたFAQの後処理を行い品質を向上させる
        
        Args:
            faqs: 生成されたFAQリスト
            source_type: ソースタイプ (pdf, slack, etc.)
            source_url: ソースへのURL
            
        Returns:
            処理後のFAQリスト
        """
        if not faqs:
            return []
        
        processed_faqs = []
        
        for faq in faqs:
            question = faq.get("question", "")
            answer = faq.get("answer", "")
            
            if not question or not answer:
                continue  # 質問か回答が空の場合はスキップ
            
            # 1. 質問の改善
            processed_question = FAQPostProcessor._improve_question(question)
            
            # 2. 回答の改善
            processed_answer = FAQPostProcessor._improve_answer(answer, source_type, source_url)
            
            # 改善された結果を追加
            processed_faqs.append({
                **faq,
                "question": processed_question,
                "answer": processed_answer
            })
        
        # 3. 重複排除
        final_faqs = FAQPostProcessor._remove_duplicates(processed_faqs)
        
        return final_faqs
    
    @staticmethod
    def _improve_question(question: str) -> str:
        """質問文を改善"""
        # 質問が空でないことを確認
        if not question or not question.strip():
            return "不明な質問"
        
        # 質問の整形
        improved = question.strip()
        
        # 文末が疑問形になっていない場合、追加する
        if not improved.endswith('?') and not improved.endswith('？'):
            # 既に疑問文の形式になっているか確認
            if any(q in improved.lower() for q in ["どう", "なぜ", "どこ", "いつ", "だれ", "何", "ですか"]):
                # 日本語の文末なら「？」を追加
                improved += '？'
            else:
                # そうでなければ「？」を追加
                improved += '?'
        
        # 質問が長すぎる場合は簡潔にする
        if len(improved) > 100:
            # ピリオドやカンマで区切られた最初の部分だけを抽出
            match = re.search(r'^[^.;,?!]+[.;,?!]', improved)
            if match:
                improved = match.group(0)
            else:
                # 区切りがなければ100文字で切る
                improved = improved[:97] + '...'
        
        # 質問が大文字で始まることを確認
        if improved and improved[0].islower():
            improved = improved[0].upper() + improved[1:]
        
        return improved
    
    @staticmethod
    def _improve_answer(answer: str, source_type: str, source_url: str) -> str:
        """回答文を改善"""
        # 回答が空でないことを確認
        if not answer or not answer.strip():
            return "回答が見つかりませんでした。"
        
        # 回答の整形
        improved = answer.strip()
        
        # 冒頭の余分な表現を削除
        improved = re.sub(r'^(はい|いいえ|Yes|No)(、|\.|,|\s)', '', improved)
        
        # 回答が適切に終わっているか確認
        if not improved.endswith('.') and not improved.endswith('。'):
            # 文末が明確な終わりではない場合、適切な文末を追加
            if re.search(r'[a-zA-Z0-9]$', improved):
                improved += '.'
            elif re.search(r'[ぁ-んァ-ン一-龯々]$', improved):
                improved += '。'
        
        # 元の資料への参照を追加
        if source_url and not any(ref in improved for ref in ["参照", "詳細は", "マニュアル", "ドキュメント", "スレッド", "会話"]):
            source_type_ja = "ドキュメント" if source_type == "pdf" else "Slack会話"
            improved += f"\n\n詳細については元の{source_type_ja}を参照してください。"
        
        return improved
    
    @staticmethod
    def _remove_duplicates(faqs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """重複または非常に類似したFAQを削除"""
        if not faqs:
            return []
        
        # すでに処理済みの質問
        processed_questions = {}
        unique_faqs = []
        
        for faq in faqs:
            question = faq["question"]
            
            # 既存の質問との類似度をチェック
            is_duplicate = False
            best_match = None
            highest_similarity = 0.0
            
            for existing_q in processed_questions.keys():
                similarity = FAQPostProcessor._calculate_similarity(question, existing_q)
                if similarity > 0.7:  # 70%以上の類似度なら重複と見なす
                    is_duplicate = True
                    if similarity > highest_similarity:
                        highest_similarity = similarity
                        best_match = existing_q
            
            if is_duplicate and best_match:
                # 既存のFAQと結合（より長い回答を採用）
                existing_idx = processed_questions[best_match]
                if len(faq["answer"]) > len(unique_faqs[existing_idx]["answer"]):
                    unique_faqs[existing_idx]["answer"] = faq["answer"]
            else:
                # 新しいFAQとして追加
                processed_questions[question] = len(unique_faqs)
                unique_faqs.append(faq)
        
        return unique_faqs
    
    @staticmethod
    def _calculate_similarity(text1: str, text2: str) -> float:
        """2つのテキスト間の類似度を計算（0〜1の値）"""
        # 文字ベースのn-gramを作成
        def get_ngrams(text, n=3):
            return [text[i:i+n] for i in range(len(text) - n + 1) if i+n <= len(text)]
        
        # 各テキストのn-gramを取得
        ngrams1 = set(get_ngrams(text1))
        ngrams2 = set(get_ngrams(text2))
        
        # 共通のn-gramの数
        intersection = len(ngrams1.intersection(ngrams2))
        
        # 両方のn-gramの合計
        union = len(ngrams1.union(ngrams2))
        
        if union == 0:
            return 0
        
        return intersection / union


class LLMOutputParser:
    """LLMの出力を解析するユーティリティクラス"""
    
    @staticmethod
    def extract_json_from_markdown(text: str) -> str:
        """
        マークダウン形式のテキストからJSON部分を抽出
        
        Args:
            text: LLMから返された生のテキスト
            
        Returns:
            抽出されたJSON文字列
        """
        # JSONブロックを検出する正規表現
        json_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        
        # JSONブロックを検索
        matches = re.findall(json_block_pattern, text)
        
        if matches:
            # 最初に見つかったJSONブロックを返す
            return matches[0].strip()
        
        # マークダウンブロックが見つからない場合、別のアプローチを試す
        # [...]や{...}で囲まれた部分を探す
        if '[' in text and ']' in text:
            array_pattern = r'\[\s*\{.*\}\s*\]'
            array_matches = re.search(array_pattern, text, re.DOTALL)
            if array_matches:
                return array_matches.group(0)
        
        # JSON部分が見つからない場合、元のテキストを返す
        return text
    
    @staticmethod
    def parse_faq_response(llm_response: str) -> List[Dict[str, Any]]:
        """
        LLMの回答からFAQを解析
        
        Args:
            llm_response: LLM出力の全テキスト
            
        Returns:
            解析されたFAQリスト
        """
        try:
            # JSONブロックの抽出
            json_text = LLMOutputParser.extract_json_from_markdown(llm_response)
            
            # Chain of Thoughtの出力から最後のJSONブロックを抽出
            if "思考過程" in llm_response and "```json" not in json_text:
                # 思考過程以降のテキストから再度JSONを探す
                thought_parts = llm_response.split("思考過程:")
                if len(thought_parts) > 1:
                    json_text = LLMOutputParser.extract_json_from_markdown(thought_parts[1])
            
            # "のようなJSONが得られます" などの表現があればその後のJSON部分を探す
            if "得られます" in llm_response and "```json" not in json_text:
                parts = re.split(r'得られます[：:]', llm_response)
                if len(parts) > 1:
                    json_text = LLMOutputParser.extract_json_from_markdown(parts[1])
            
            # JSONのパース
            faqs = json.loads(json_text)
            
            # 結果の検証
            if not isinstance(faqs, list):
                raise ValueError("JSONの解析結果がリスト形式ではありません")
            
            # 各FAQの構造を検証
            valid_faqs = []
            for faq in faqs:
                if isinstance(faq, dict) and "question" in faq and "answer" in faq:
                    valid_faqs.append(faq)
            
            return valid_faqs
            
        except Exception as e:
            print(f"FAQ解析中にエラーが発生しました: {e}")
            print(f"解析対象のテキスト: {llm_response[:100]}...")
            # エラー時は空のリストを返す
            return []


# JSONモジュールをインポート
import json