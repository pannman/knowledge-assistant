import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime, timedelta

class SlackClient:
    """Slack APIクライアント"""
    
    def __init__(self):
        """Slack APIクライアントの初期化"""
        slack_token = os.getenv("SLACK_API_TOKEN")
        if not slack_token:
            raise ValueError("Slack API token not found in environment variables")
        
        self.client = WebClient(token=slack_token)
    
    def get_channel_history(self, channel_id, days_back=30):
        """チャンネルの会話履歴を取得"""
        try:
            # まずチャンネルに参加を試みる
            self.join_channel(channel_id)
            
            # 以降は既存のコード
            oldest_time = datetime.now() - timedelta(days=days_back)
            oldest_ts = oldest_time.timestamp()
            
            result = self.client.conversations_history(
                channel=channel_id,
                oldest=str(oldest_ts)
            )
            
            messages = result["messages"]
            print("\n📥 取得したメッセージ一覧:")
            for i, msg in enumerate(messages, 1):
                print(f"\n----- メッセージ #{i} -----")
                print(f"• タイムスタンプ: {msg.get('ts')}")
                print(f"• ユーザー: {self.get_user_name(msg.get('user', 'Unknown'))}")
                print(f"• スレッド?: {'はい' if msg.get('thread_ts') else 'いいえ'}")
                if msg.get('thread_ts'):
                    print(f"• スレッドID: {msg.get('thread_ts')}")
                    print(f"• 返信数: {msg.get('reply_count', 0)}")
                print(f"• テキスト: {msg.get('text', '')[:100]}...")
                print("-" * 50)
            
            print(f"\n📊 合計メッセージ数: {len(messages)}")
            return messages
        
        except SlackApiError as e:
            print(f"Error fetching conversations: {e}")
            return []
    
    def get_thread_replies(self, channel_id, thread_ts):
        """スレッドの返信を取得"""
        try:
            result = self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts
            )
            
            return result["messages"]
        
        except SlackApiError as e:
            print(f"Error fetching thread replies: {e}")
            return []
    
    def format_conversation(self, messages, thread_id=None):
        """会話を整形して返す"""
        formatted_messages = []
        processed_threads = set()  # 処理済みスレッドを追跡
        
        print("\n🧵 メッセージ処理を開始...")
        
        for msg in messages:
            # システムメッセージをスキップ
            if msg.get('subtype') in ['channel_join', 'channel_leave', 'bot_message']:
                continue
            
            # スレッドメッセージの場合、親メッセージのみを処理
            if thread_id and msg.get("thread_ts") != thread_id:
                continue
            
            # スレッドの場合
            thread_ts = msg.get("thread_ts")
            if not thread_id and thread_ts:
                # 既に処理済みのスレッドはスキップ
                if thread_ts in processed_threads:
                    continue
                
                processed_threads.add(thread_ts)
                
                print(f"\n📎 スレッド {thread_ts} の処理中...")
                print(f"  • 返信数: {msg.get('reply_count', 0)}")
                
                thread_messages = self.get_thread_replies(
                    channel_id=os.getenv("SLACK_CHANNEL_ID"),
                    thread_ts=thread_ts
                )
                
                # システムメッセージを除外してスレッドメッセージを整形
                thread_text = "\n".join([
                    f"{self.get_user_name(tm.get('user', 'Unknown'))}: {tm.get('text', '')}"
                    for tm in thread_messages
                    if not tm.get('subtype') in ['channel_join', 'channel_leave', 'bot_message']
                ])
                
                if thread_text.strip():  # 空のスレッドを除外
                    formatted_messages.append({
                        "thread_id": thread_ts,
                        "text": thread_text,
                        "timestamp": float(msg.get("ts", 0)),
                        "permalink": self.get_permalink(
                            os.getenv("SLACK_CHANNEL_ID"),
                            thread_ts
                        )
                    })
                    print(f"  ✅ スレッド {thread_ts} の処理完了")
            
            # スレッドでない単独メッセージの場合
            elif not thread_id and not thread_ts and msg.get('user'):
                print(f"\n💬 単独メッセージの処理中...")
                print(f"  • ユーザー: {self.get_user_name(msg.get('user', 'Unknown'))}")
                print(f"  • メッセージ: {msg.get('text', '')[:100]}...")
                
                formatted_messages.append({
                    "thread_id": msg.get("ts"),
                    "text": f"{self.get_user_name(msg.get('user', 'Unknown'))}: {msg.get('text', '')}",
                    "timestamp": float(msg.get("ts", 0)),
                    "permalink": self.get_permalink(
                        os.getenv("SLACK_CHANNEL_ID"),
                        msg.get("ts")
                    )
                })
                
                print(f"  ✅ メッセージの処理完了")
        
        print(f"\n📊 処理完了したメッセージ数: {len(formatted_messages)}")
        return formatted_messages
    
    def get_user_name(self, user_id):
        """ユーザーIDから名前を取得"""
        try:
            result = self.client.users_info(user=user_id)
            user = result["user"]
            # 優先順位: real_name > display_name > name > user_id
            return (
                user.get("real_name") or 
                user.get("profile", {}).get("display_name") or 
                user.get("name") or 
                user_id or 
                "Unknown User"
            )
        except SlackApiError as e:
            print(f"Error fetching user info: {e}")
            return "Unknown User"
    
    def get_permalink(self, channel_id, message_ts):
        """メッセージのパーマリンクを取得"""
        try:
            result = self.client.chat_getPermalink(
                channel=channel_id,
                message_ts=message_ts
            )
            return result["permalink"]
        except SlackApiError:
            return None
    
    def join_channel(self, channel_id):
        """チャンネルにボットを参加させる"""
        try:
            self.client.conversations_join(channel=channel_id)
            return True
        except SlackApiError as e:
            print(f"Error joining channel: {e}")
            return False