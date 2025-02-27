import os
import uuid
import json
from typing import List, Dict, Any
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
)
from datetime import datetime
import pytz

class AzureSearchClient:
    """Azure Cognitive Searchクライアント"""
    
    def __init__(self):
        """Azure Searchクライアントの初期化"""
        self.endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.key = os.getenv("AZURE_SEARCH_API_KEY")
        self.pdf_index_name = "pdf-faq-index"
        self.slack_index_name = "slack-faq-index"
        
        if not self.endpoint or not self.key:
            raise ValueError("Azure Search credentials not found in environment variables")
        
        # 認証情報の作成
        self.credential = AzureKeyCredential(self.key)
        
        # インデックスクライアントの作成
        self.index_client = SearchIndexClient(
            endpoint=self.endpoint,
            credential=self.credential
        )
        
        # インデックスが存在しない場合は作成
        self._create_indexes_if_not_exist()
        
        # PDFインデックス用の検索クライアント
        self.pdf_search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=self.pdf_index_name,
            credential=self.credential
        )
        
        # Slackインデックス用の検索クライアント
        self.slack_search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=self.slack_index_name,
            credential=self.credential
        )
    
    def _create_indexes_if_not_exist(self):
        """インデックスが存在しない場合は作成"""
        # 既存のインデックスを取得
        existing_indexes = [index.name for index in self.index_client.list_indexes()]
        
        # PDFインデックスの作成（存在しない場合）
        if self.pdf_index_name not in existing_indexes:
            pdf_index = SearchIndex(
                name=self.pdf_index_name,
                fields=[
                    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                    SearchableField(name="question", type=SearchFieldDataType.String, 
                                   analyzer_name="ja.microsoft"),
                    SearchableField(name="answer", type=SearchFieldDataType.String, 
                                   analyzer_name="ja.microsoft"),
                    SimpleField(name="source_id", type=SearchFieldDataType.String),
                    SimpleField(name="source_url", type=SearchFieldDataType.String),
                    SearchableField(name="content_chunk", type=SearchFieldDataType.String, 
                                   analyzer_name="ja.microsoft"),
                    SearchableField(name="summary", type=SearchFieldDataType.String, 
                                   analyzer_name="ja.microsoft"),
                    SimpleField(name="page_num", type=SearchFieldDataType.Int32),
                    SimpleField(name="created_at", type=SearchFieldDataType.DateTimeOffset)
                ]
            )
            self.index_client.create_index(pdf_index)
        
        # Slackインデックスの作成（存在しない場合）
        if self.slack_index_name not in existing_indexes:
            slack_index = SearchIndex(
                name=self.slack_index_name,
                fields=[
                    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                    SearchableField(name="question", type=SearchFieldDataType.String, 
                                   analyzer_name="ja.microsoft"),
                    SearchableField(name="answer", type=SearchFieldDataType.String, 
                                   analyzer_name="ja.microsoft"),
                    SimpleField(name="thread_id", type=SearchFieldDataType.String),
                    SimpleField(name="channel_id", type=SearchFieldDataType.String),
                    SimpleField(name="source_url", type=SearchFieldDataType.String),
                    SearchableField(name="content_chunk", type=SearchFieldDataType.String, 
                                   analyzer_name="ja.microsoft"),
                    SearchableField(name="summary", type=SearchFieldDataType.String, 
                                   analyzer_name="ja.microsoft"),
                    SimpleField(name="created_at", type=SearchFieldDataType.DateTimeOffset)
                ]
            )
            self.index_client.create_index(slack_index)
    
    def upload_pdf_faqs(self, faqs: List[Dict[str, Any]]) -> int:
        """PDFからのFAQをアップロード"""
        if not faqs:
            return 0
        
        documents = []
        for faq in faqs:
            # created_atの処理を追加
            created_at = faq.get("created_at")
            if created_at:
                try:
                    if isinstance(created_at, str):
                        # 文字列からdatetimeに変換
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    # 必ずUTCタイムゾーンを設定
                    if created_at.tzinfo is None:
                        created_at = pytz.UTC.localize(created_at)  # pytzを使用
                    # 明示的にUTCオフセットを含むISO形式に変換
                    created_at = created_at.astimezone(pytz.UTC).isoformat()  # pytzを使用
                    if '+00:00' not in created_at and 'Z' not in created_at:
                        created_at += '+00:00'
                except Exception as e:
                    print(f"Date conversion error: {e}")
                    created_at = datetime.now(pytz.UTC).isoformat()  # pytzを使用
            else:
                # created_atがない場合は現在時刻を使用
                created_at = datetime.now(pytz.UTC).isoformat()  # pytzを使用

            doc = {
                "id": str(uuid.uuid4()),
                "question": faq["question"],
                "answer": faq["answer"],
                "source_id": faq["source_id"],
                "source_url": faq["source_url"],
                "content_chunk": faq.get("content_chunk", ""),
                "summary": faq.get("summary", ""),
                "page_num": faq.get("page_num", 0),
                "created_at": created_at  # 処理済みの日付を設定
            }
            documents.append(doc)
        
        try:
            result = self.pdf_search_client.upload_documents(documents)
            return len(result)
        except Exception as e:
            print(f"Error uploading PDF FAQs: {e}")
            return 0
    
    def upload_slack_faqs(self, faqs: List[Dict[str, Any]]) -> int:
        """SlackからのFAQをアップロード"""
        if not faqs:
            return 0
        
        documents = []
        for faq in faqs:
            # created_atの処理を修正
            created_at = faq.get("created_at")
            if created_at:
                try:
                    if isinstance(created_at, str):
                        # 文字列からdatetimeに変換
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    # 必ずUTCタイムゾーンを設定
                    if created_at.tzinfo is None:
                        created_at = pytz.UTC.localize(created_at)  # pytzを使用
                    # 明示的にUTCオフセットを含むISO形式に変換
                    created_at = created_at.astimezone(pytz.UTC).isoformat()  # pytzを使用
                    if '+00:00' not in created_at and 'Z' not in created_at:
                        created_at += '+00:00'
                except Exception as e:
                    print(f"Date conversion error: {e}")
                    created_at = datetime.now(pytz.UTC).isoformat()  # pytzを使用
            else:
                # created_atがない場合は現在時刻を使用
                created_at = datetime.now(pytz.UTC).isoformat()  # pytzを使用

            doc = {
                "id": str(uuid.uuid4()),
                "question": faq["question"],
                "answer": faq["answer"],
                "thread_id": faq["thread_id"],
                "channel_id": faq.get("channel_id", ""),
                "source_url": faq["source_url"],
                "content_chunk": faq.get("content_chunk", ""),
                "summary": faq.get("summary", ""),
                "created_at": created_at  # 処理済みの日付を設定
            }
            documents.append(doc)
        
        try:
            result = self.slack_search_client.upload_documents(documents)
            return len(result)
        except Exception as e:
            print(f"Error uploading Slack FAQs: {e}")
            return 0
    
    def search(self, query: str, top: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """PDFとSlackの両方のインデックスを検索"""
        results = {
            "pdf": [],
            "slack": []
        }
        
        # PDFインデックスを検索
        try:
            pdf_results = self.pdf_search_client.search(
                search_text=query,
                select="id,question,answer,source_id,source_url,summary",
                top=top
            )
            
            for result in pdf_results:
                results["pdf"].append(dict(result))
        except Exception as e:
            print(f"Error searching PDF index: {e}")
        
        # Slackインデックスを検索
        try:
            slack_results = self.slack_search_client.search(
                search_text=query,
                select="id,question,answer,thread_id,source_url,summary",
                top=top
            )
            
            for result in slack_results:
                results["slack"].append(dict(result))
        except Exception as e:
            print(f"Error searching Slack index: {e}")
        
        return results