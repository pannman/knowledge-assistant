"""
テキスト前処理モジュール
PDF文書やSlack会話など、異なるソースからのテキストを前処理するユーティリティ
"""

import re
from typing import Dict, List, Tuple, Set, Any


class PDFTextProcessor:
    """PDFテキストの前処理を行うクラス"""
    
    @staticmethod
    def process(text: str) -> Dict[str, Any]:
        """
        PDFテキストを前処理して構造情報を抽出
        
        Args:
            text: PDFから抽出した生テキスト
            
        Returns:
            処理結果を含む辞書（元テキスト、構造情報など）
        """
        # 結果を格納する辞書
        result = {
            "original_text": text,
            "headers": [],
            "bullet_points": [],
            "important_terms": set(),
            "enhanced_text": ""
        }
        
        try:
            # 1. セクション構造（見出し）の検出
            lines = text.split('\n')
            for i, line in enumerate(lines):
                # 見出しの条件:
                # - 短い行（50文字未満）
                # - 次の行が空行、またはすべて大文字/数字から始まる
                # - 記号で終わらない（文章の一部でない）
                if (len(line.strip()) < 50 and line.strip() and 
                    (i+1 < len(lines) and (not lines[i+1].strip() or lines[i+1].strip()[0].isdigit())) and
                    not line.strip()[-1] in [',', '.', '、', '。']):
                    result["headers"].append(line.strip())
                
                # または明確な見出しパターン（数字+タイトル）
                if re.match(r'^\s*(\d+\.|\d+\-|\d+:|第\d+章|[①-⑩]\.)\s*\w+', line):
                    result["headers"].append(line.strip())
            
            # 2. 箇条書きリストの検出
            bullet_pattern = re.compile(r'^\s*([•\-\*・]|\d+\.|[①-⑩]\.?)\s+\w+')
            
            for i, line in enumerate(lines):
                if bullet_pattern.match(line):
                    result["bullet_points"].append(line.strip())
            
            # 3. 重要キーワードの検出
            # 3.1 引用符で囲まれた語句
            quoted_terms = re.findall(r'「([^」]{2,})」|"([^"]{2,})"', text)
            for term_group in quoted_terms:
                for term in term_group:
                    if term and len(term) > 1:
                        result["important_terms"].add(term)
            
            # 3.2 専門用語っぽい複合語（カタカナ＋漢字など）
            compound_terms = re.findall(r'[ァ-ヶー]+[一-龯々]+|[一-龯々]+[ァ-ヶー]+', text)
            for term in compound_terms:
                if len(term) > 3:  # 短すぎる語は除外
                    result["important_terms"].add(term)
            
            # 3.3 太字や強調されたテキスト (マークダウン形式の検出)
            markdown_emphasis = re.findall(r'\*\*([^*]+)\*\*|\*([^*]+)\*|__([^_]+)__|_([^_]+)_', text)
            for emphasis_group in markdown_emphasis:
                for term in emphasis_group:
                    if term and len(term) > 1:
                        result["important_terms"].add(term)
            
            # 4. 検出情報を使ってコンテキスト強化
            enhanced_text = text
            
            # 構造情報のサマリーを追加
            structure_summary = "\n\n=== 文書構造の分析 ===\n"
            
            if result["headers"]:
                structure_summary += "\n【検出された見出し】\n"
                for header in result["headers"][:7]:  # 最初の7つのみ
                    structure_summary += f"- {header}\n"
            
            if result["bullet_points"]:
                structure_summary += "\n【検出された箇条書き/手順】\n"
                for point in result["bullet_points"][:7]:  # 最初の7つのみ
                    structure_summary += f"{point}\n"
            
            if result["important_terms"]:
                structure_summary += "\n【検出された重要用語】\n"
                for term in list(result["important_terms"])[:10]:  # 最初の10個のみ
                    structure_summary += f"- {term}\n"
            
            result["enhanced_text"] = enhanced_text + structure_summary
            
            return result
            
        except Exception as e:
            print(f"Error in PDFTextProcessor: {e}")
            # エラーが発生した場合は元のテキストをそのまま返す
            result["enhanced_text"] = text
            return result


class SlackConversationProcessor:
    """Slack会話の前処理を行うクラス"""
    
    @staticmethod
    def process(conversation_text: str) -> Dict[str, Any]:
        """
        Slack会話を前処理して構造情報を抽出
        
        Args:
            conversation_text: Slack会話の生テキスト
            
        Returns:
            処理結果を含む辞書（元テキスト、構造情報など）
        """
        # 結果を格納する辞書
        result = {
            "original_text": conversation_text,
            "structured_messages": [],
            "qa_pairs": [],
            "participants": set(),
            "enhanced_text": ""
        }
        
        try:
            # 1. 会話構造を検出して整形
            # スレッド形式を検出（ユーザー名：メッセージ の形式を探す）
            lines = conversation_text.split('\n')
            structured_convo = []
            current_speaker = None
            current_message = []
            
            for line in lines:
                # ユーザー名：メッセージ形式の行を検出
                if ':' in line and len(line.split(':', 1)[0]) < 30:
                    # 前のスピーカーのメッセージを保存
                    if current_speaker and current_message:
                        structured_convo.append({
                            "speaker": current_speaker,
                            "message": "\n".join(current_message)
                        })
                    
                    # 新しいスピーカーとメッセージを開始
                    parts = line.split(':', 1)
                    current_speaker = parts[0].strip()
                    result["participants"].add(current_speaker)
                    current_message = [parts[1].strip()] if len(parts) > 1 else []
                else:
                    # 現在のメッセージの続き
                    if current_speaker:
                        current_message.append(line)
            
            # 最後のメッセージを追加
            if current_speaker and current_message:
                structured_convo.append({
                    "speaker": current_speaker,
                    "message": "\n".join(current_message)
                })
            
            result["structured_messages"] = structured_convo
            
            # 2. 質問と回答のパターンを検出
            question_indicators = [
                '?', '？', 'how', 'what', 'when', 'where', 'why', 'who', 'which', 
                'could you', 'can you', 'どう', 'なぜ', 'どこ', 'いつ', 'だれ', '何', 
                '教えて', 'ください', 'できますか', 'できる？', 'ですか'
            ]
            
            for i in range(len(structured_convo) - 1):
                current = structured_convo[i]
                next_msg = structured_convo[i + 1]
                
                # メッセージが質問の可能性があるか判断
                is_question = any(q in current["message"].lower() for q in question_indicators)
                
                if is_question:
                    result["qa_pairs"].append({
                        "question_by": current["speaker"],
                        "question": current["message"],
                        "answer_by": next_msg["speaker"],
                        "answer": next_msg["message"]
                    })
            
            # 3. 検出されたQ&Aペアを元にコンテキスト強化
            enhanced_text = conversation_text
            
            # Q&Aペアが検出された場合、その情報を追加
            if result["qa_pairs"]:
                qa_summary = "\n\n=== 検出された質問と回答のパターン ===\n"
                for i, qa in enumerate(result["qa_pairs"]):
                    qa_summary += f"\n【質問{i+1}】 ({qa['question_by']}): {qa['question']}\n"
                    qa_summary += f"【回答{i+1}】 ({qa['answer_by']}): {qa['answer']}\n"
                
                enhanced_text += qa_summary
            
            # 参加者情報を追加
            if result["participants"]:
                participant_summary = "\n\n=== 会話参加者 ===\n"
                for participant in result["participants"]:
                    participant_summary += f"- {participant}\n"
                
                enhanced_text += participant_summary
            
            result["enhanced_text"] = enhanced_text
            
            return result
            
        except Exception as e:
            print(f"Error in SlackConversationProcessor: {e}")
            # エラーが発生した場合は元のテキストをそのまま返す
            result["enhanced_text"] = conversation_text
            return result