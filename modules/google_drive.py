import os
import io
import tempfile
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

class GoogleDriveClient:
    """Google Drive APIクライアント"""
    
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    
    def __init__(self):
        """Google Drive APIクライアントの初期化"""
        self.creds = None
        self.service = None
        self.authenticate()
    
    def authenticate(self):
        """Google APIの認証"""
        # 環境変数から認証情報を取得
        token_json = os.getenv('GOOGLE_TOKEN_JSON')
        credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        
        # トークンファイルが存在する場合、認証情報を読み込む
        if token_json:
            self.creds = Credentials.from_authorized_user_info(eval(token_json), self.SCOPES)
        
        # 認証情報が無効な場合、再認証を行う
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not credentials_json:
                    raise ValueError("Google API credentials not found in environment variables")
                
                flow = InstalledAppFlow.from_client_config(
                    eval(credentials_json), self.SCOPES)
                self.creds = flow.run_local_server(port=0)
            
            # 新しいトークンを環境変数に保存
            os.environ['GOOGLE_TOKEN_JSON'] = str(self.creds.to_json())
        
        # APIサービスの構築
        self.service = build('drive', 'v3', credentials=self.creds)
    
    def list_files(self, folder_id, file_type="application/pdf"):
        """指定フォルダ内のファイルを一覧表示"""
        query = f"'{folder_id}' in parents and trashed = false"
        if file_type:
            query += f" and mimeType='{file_type}'"
        
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, webViewLink)'
        ).execute()
        
        return results.get('files', [])
    
    def download_file(self, file_id):
        """ファイルをダウンロードしてテンポラリファイルとして保存"""
        request = self.service.files().get_media(fileId=file_id)
        
        # テンポラリファイルを作成
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        
        # ファイルをダウンロード
        downloader = MediaIoBaseDownload(temp_file, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        temp_file.close()
        return temp_file.name
    
    def get_file_metadata(self, file_id):
        """ファイルのメタデータを取得"""
        return self.service.files().get(
            fileId=file_id, 
            fields='id, name, mimeType, webViewLink'
        ).execute()