import streamlit as st
import os
from datetime import datetime
from dotenv import load_dotenv
from modules.google_drive import GoogleDriveClient
from modules.slack_api import SlackClient
from modules.pdf_processor import PDFProcessor
from modules.faq_generator import FAQGenerator
from modules.azure_search import AzureSearchClient
from modules.rag_engine import RAGEngine

# 環境変数のロード
load_dotenv()

# ページ設定
st.set_page_config(
    page_title="社内ナレッジ検索アシスタント",
    page_icon="🔍",
    layout="wide",
)

# アプリケーションタイトル
st.title("社内ナレッジ検索アシスタント")
st.caption("社内マニュアルやSlackのやり取りからあなたの質問に答えます")

# Google Driveからのデータ更新処理
def update_from_google_drive():
    """Google Driveからデータを取得し、FAQを生成してインデックス化"""
    try:
        # クライアントの初期化
        drive_client = GoogleDriveClient()
        pdf_processor = PDFProcessor()
        faq_generator = FAQGenerator()
        azure_search = AzureSearchClient()
        
        # フォルダIDの取得
        folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        if not folder_id:
            return "Google DriveフォルダIDが設定されていません。"
        
        # ファイル一覧の取得
        files = drive_client.list_files(folder_id)
        if not files:
            return "指定フォルダにPDFファイルが見つかりませんでした。"
        
        total_faqs = 0
        
        # 各ファイルの処理
        for file in files:
            # ファイルのダウンロード
            file_path = drive_client.download_file(file["id"])
            
            # メタデータの取得
            metadata = pdf_processor.get_document_metadata(file_path)
            
            # テキストの抽出
            chunks = pdf_processor.extract_text(file_path)
            
            # 各チャンクからFAQを生成
            for chunk in chunks:
                chunk_text = chunk["text"]
                page_num = chunk["page_num"]
                
                # 要約の生成
                summary = faq_generator.generate_summary(chunk_text)
                
                # FAQの生成
                faqs = faq_generator.generate_faqs_from_text(
                    text=chunk_text,
                    source_type="pdf",
                    source_id=file["id"],
                    source_url=file["webViewLink"],
                    context=f"このテキストは{metadata['title']}のページ{page_num}から抽出されました。"
                )
                
                # FAQにメタデータを追加
                for faq in faqs:
                    faq["content_chunk"] = chunk_text
                    faq["summary"] = summary
                    faq["page_num"] = page_num
                    faq["created_at"] = datetime.now().isoformat()
                
                # FAQのアップロード
                if faqs:
                    total_faqs += azure_search.upload_pdf_faqs(faqs)
            
            # 一時ファイルの削除
            os.unlink(file_path)
        
        return f"処理完了: {len(files)}ファイルから{total_faqs}件のFAQを生成しました。"
    
    except Exception as e:
        return f"エラーが発生しました: {str(e)}"

# Slackからのデータ更新処理
def update_from_slack():
    """Slackからデータを取得し、FAQを生成してインデックス化"""
    try:
        # クライアントの初期化
        slack_client = SlackClient()
        faq_generator = FAQGenerator()
        azure_search = AzureSearchClient()
        
        # チャンネルIDの取得
        channel_id = os.getenv("SLACK_CHANNEL_ID")
        if not channel_id:
            return "SlackチャンネルIDが設定されていません。"
        
        # 会話履歴の取得
        messages = slack_client.get_channel_history(channel_id)
        if not messages:
            return "指定チャンネルのメッセージが見つかりませんでした。"
        
        # 会話の整形
        conversations = slack_client.format_conversation(messages)
        
        total_faqs = 0
        
        # 各会話の処理
        for conv in conversations:
            # 会話テキスト
            conv_text = conv["text"]
            thread_id = conv["thread_id"]
            permalink = conv["permalink"]
            
            # 要約の生成
            summary = faq_generator.generate_summary(conv_text)
            
            # FAQの生成
            faqs = faq_generator.generate_faqs_from_text(
                text=conv_text,
                source_type="slack",
                source_id=thread_id,
                source_url=permalink
            )
            
            # FAQにメタデータを追加
            for faq in faqs:
                faq["content_chunk"] = conv_text
                faq["summary"] = summary
                faq["thread_id"] = thread_id
                faq["channel_id"] = channel_id
                faq["created_at"] = datetime.now().isoformat()
            
            # FAQのアップロード
            if faqs:
                total_faqs += azure_search.upload_slack_faqs(faqs)
        
        return f"処理完了: {len(conversations)}の会話から{total_faqs}件のFAQを生成しました。"
    
    except Exception as e:
        return f"エラーが発生しました: {str(e)}"

# サイドバー - 設定とアクション
with st.sidebar:
    st.header("データ更新")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Google Driveから更新", use_container_width=True):
            with st.spinner("Google Driveからデータを取得中..."):
                try:
                    result = update_from_google_drive()
                    st.success(result)
                except Exception as e:
                    st.error(f"エラーが発生しました: {str(e)}")
    
    with col2:
        if st.button("Slackから更新", use_container_width=True):
            with st.spinner("Slackからデータを取得中..."):
                try:
                    result = update_from_slack()
                    st.success(result)
                except Exception as e:
                    st.error(f"エラーが発生しました: {str(e)}")
    
    st.divider()
    
    # 設定
    st.header("設定")
    
    # Google Drive設定
    st.subheader("Google Drive")
    drive_folder = st.text_input("フォルダID", value=os.getenv("GOOGLE_DRIVE_FOLDER_ID", ""))
    
    # Slack設定
    st.subheader("Slack")
    slack_channel = st.text_input("チャンネルID", value=os.getenv("SLACK_CHANNEL_ID", ""))
    
    # 保存ボタン
    if st.button("設定を保存", use_container_width=True):
        # 一時的に環境変数を更新
        os.environ["GOOGLE_DRIVE_FOLDER_ID"] = drive_folder
        os.environ["SLACK_CHANNEL_ID"] = slack_channel
        st.success("設定を保存しました！")

# メインエリア - チャットインターフェース
st.divider()

# RAGエンジンの初期化
try:
    rag_engine = RAGEngine()
except Exception as e:
    st.error(f"RAGエンジンの初期化に失敗しました: {str(e)}")
    rag_engine = None

# チャット履歴の初期化
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "こんにちは！社内ナレッジに関する質問があればお答えします。"}
    ]

# チャット履歴の表示
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ユーザー入力
if prompt := st.chat_input("質問を入力してください"):
    # ユーザーメッセージをチャット履歴に追加
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # ユーザーメッセージを表示
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # AIの応答を生成
    with st.chat_message("assistant"):
        if rag_engine:
            message_placeholder = st.empty()
            with st.spinner("回答を生成中..."):
                try:
                    response, sources = rag_engine.generate_response(prompt)
                    
                    # 回答と参照ソースを表示
                    message_placeholder.markdown(response)
                    
                    # 参照ソースの表示
                    if sources:
                        st.divider()
                        st.subheader("参照ソース")
                        for source in sources:
                            if source["type"] == "pdf":
                                st.markdown(f"📄 **PDFソース**: [{source['title']}]({source['url']})")
                            elif source["type"] == "slack":
                                st.markdown(f"💬 **Slackスレッド**: [スレッドを見る]({source['url']})")
                    
                    # 回答をチャット履歴に追加
                    full_response = response + "\n\n**参照ソース**:\n" + "\n".join(
                        [f"- {s['title']} ({s['type']})" for s in sources]
                    ) if sources else response
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    
                except Exception as e:
                    message_placeholder.error(f"エラーが発生しました: {str(e)}")
                    st.session_state.messages.append({"role": "assistant", "content": f"申し訳ありません、エラーが発生しました: {str(e)}"})
        else:
            st.error("RAGエンジンが初期化されていないため、質問に回答できません。")
            st.session_state.messages.append({"role": "assistant", "content": "申し訳ありません、システムエラーが発生しています。"})

# フッター
st.divider()
st.caption("© 2025 社内ナレッジ検索アシスタント")