"""
改善版 非同期Pushbulletクライアント実装
WebSocket接続の安定性を向上
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Callable
import aiohttp
import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

# ロギング設定
logger = logging.getLogger(__name__)


class AsyncPushbullet:
    """非同期Pushbulletクライアント"""
    
    API_BASE = "https://api.pushbullet.com/v2"
    WS_URL = "wss://stream.pushbullet.com/websocket"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self._headers = {
            "Access-Token": api_key,
            "Content-Type": "application/json"
        }
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self._headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """APIリクエストを送信"""
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self._headers)
        
        url = f"{self.API_BASE}/{endpoint}"
        async with self.session.request(method, url, **kwargs) as response:
            response.raise_for_status()
            return await response.json()
    
    async def get_user(self) -> Dict[str, Any]:
        """ユーザー情報を取得"""
        return await self._request("GET", "users/me")
    
    async def get_devices(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """デバイス一覧を取得
        
        Args:
            active_only: Trueの場合、アクティブなデバイスのみを返す
        """
        result = await self._request("GET", "devices")
        devices = result.get("devices", [])
        
        if active_only:
            # アクティブなデバイスのみフィルタリング
            return [d for d in devices if d.get("active", False)]
        return devices
    
    async def create_device(self, nickname: str, model: str = "push-tmux") -> Dict[str, Any]:
        """新しいデバイスを作成"""
        data = {
            "nickname": nickname,
            "model": model,
            "manufacturer": "push-tmux",
            "app_version": 1,
            "icon": "desktop"
        }
        return await self._request("POST", "devices", json=data)
    
    async def delete_device(self, device_iden: str) -> None:
        """デバイスを削除"""
        await self._request("DELETE", f"devices/{device_iden}")
    
    async def push_note(self, title: str, body: str, device_iden: Optional[str] = None) -> Dict[str, Any]:
        """ノートを送信"""
        data = {
            "type": "note",
            "title": title,
            "body": body
        }
        if device_iden:
            data["device_iden"] = device_iden
        
        return await self._request("POST", "pushes", json=data)
    
    async def get_pushes(self, modified_after: Optional[float] = None, 
                         limit: int = 20, active: bool = True) -> List[Dict[str, Any]]:
        """プッシュ履歴を取得"""
        params = {"limit": limit}
        if modified_after:
            params["modified_after"] = modified_after
        if active:
            params["active"] = "true"
        
        result = await self._request("GET", "pushes", params=params)
        return result.get("pushes", [])
    
    async def dismiss_push(self, push_iden: str) -> None:
        """プッシュを既読にする"""
        data = {"dismissed": True}
        await self._request("POST", f"pushes/{push_iden}", json=data)
    
    async def close(self):
        """セッションを閉じる"""
        if self.session:
            await self.session.close()
            self.session = None


class AsyncPushbulletListener:
    """改善版 非同期Pushbulletリスナー（WebSocket）"""
    
    # 定数
    WEBSOCKET_TIMEOUT = 45  # WebSocketタイムアウト（秒） - nopは約30秒間隔なので45秒に設定
    RECONNECT_DELAY = 5     # 再接続待機時間（秒）
    MAX_RECONNECT_ATTEMPTS = 5  # 最大再接続試行回数 - 過剰な再接続を防ぐため減らす
    NOP_TIMEOUT = 90        # nopメッセージのタイムアウト（秒）
    
    def __init__(self, api_key: str, on_push: Optional[Callable] = None, debug: bool = False):
        self.api_key = api_key
        self.on_push = on_push
        self.ws_url = f"wss://stream.pushbullet.com/websocket/{api_key}"
        self.websocket = None
        self.running = False
        self.pb_client = AsyncPushbullet(api_key)
        self.last_push_time = datetime.now(timezone.utc).timestamp()
        self.debug = debug
        self.reconnect_attempts = 0
        self.processed_push_idens = set()  # 処理済みのpush idenを記録
        
        # ロギング設定
        if debug:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
        
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def is_connected(self):
        """WebSocket接続状態を確認"""
        if not self.websocket:
            return False
        
        # websocketsライブラリのバージョンによって異なる属性をチェック
        if hasattr(self.websocket, 'closed'):
            return not self.websocket.closed
        elif hasattr(self.websocket, 'state'):
            # state.value: 0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED
            from websockets.protocol import State
            return self.websocket.state == State.OPEN
        else:
            # フォールバック: websocketオブジェクトが存在すれば接続中とみなす
            return True
    
    async def connect(self):
        """WebSocketに接続（改善版）"""
        try:
            # Pushbulletサーバーはping/pongに応答しないため無効化
            # 代わりにnopメッセージでキープアライブを監視
            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=None,  # ping/pongを無効化
                close_timeout=10
            )
            self.reconnect_attempts = 0
            self.logger.info("WebSocketに接続しました")
            return True
        except Exception as e:
            self.logger.error(f"WebSocket接続失敗: {e}")
            return False
    
    async def disconnect(self):
        """WebSocketを切断"""
        self.running = False
        if self.websocket:
            try:
                await self.websocket.close()
                self.logger.info("WebSocketを正常に切断しました")
            except Exception as e:
                self.logger.error(f"WebSocket切断エラー: {e}")
        
        try:
            await self.pb_client.close()
        except Exception as e:
            self.logger.error(f"Pushbulletクライアント切断エラー: {e}")
        
        # 処理済みキャッシュをクリア（メモリリーク防止）
        # 最大100件まで保持
        if len(self.processed_push_idens) > 100:
            # 最新100件を保持
            self.processed_push_idens = set(list(self.processed_push_idens)[-100:])
    
    async def listen(self):
        """メッセージを待ち受ける（改善版）"""
        self.running = True  # リスナー開始時にフラグを立てる
        while self.running:
            try:
                # 接続を確立
                if not self.is_connected():
                    if not await self.connect():
                        if self.reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
                            self.logger.error("最大再接続試行回数に達しました")
                            break
                        
                        self.reconnect_attempts += 1
                        self.logger.info(f"再接続を試みます... ({self.reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS})")
                        await asyncio.sleep(self.RECONNECT_DELAY * self.reconnect_attempts)
                        continue
                
                # メッセージ受信ループ
                await self._receive_messages()
                
            except ConnectionClosedOK:
                self.logger.info("WebSocket接続が正常に閉じられました")
                break
            except ConnectionClosedError as e:
                self.logger.warning(f"WebSocket接続エラー: {e}")
                if self.running:
                    await asyncio.sleep(self.RECONNECT_DELAY)
            except Exception as e:
                self.logger.error(f"予期しないエラー: {e}")
                if self.running:
                    await asyncio.sleep(self.RECONNECT_DELAY)
    
    async def _receive_messages(self):
        """メッセージ受信処理"""
        last_nop_time = datetime.now(timezone.utc)
        
        while self.running and self.websocket:
            try:
                # タイムアウト付きでメッセージを待つ
                message = await asyncio.wait_for(
                    self.websocket.recv(), 
                    timeout=self.WEBSOCKET_TIMEOUT
                )
                
                data = json.loads(message)
                message_type = data.get("type")
                
                if self.debug:
                    self.logger.debug(f"受信: {message_type} - {data}")
                
                # nop（キープアライブ）の処理
                if message_type == "nop":
                    last_nop_time = datetime.now(timezone.utc)
                    self.logger.debug("キープアライブ（nop）を受信")
                    continue
                
                # tickleメッセージの処理
                elif message_type == "tickle" and data.get("subtype") == "push":
                    self.logger.info("新しいプッシュ通知（tickle）を受信")
                    await self._handle_tickle()
                
                # pushメッセージの直接処理
                elif message_type == "push" and self.on_push:
                    push_data = data.get("push", {})
                    # 有効なpushメッセージかチェック
                    if push_data and isinstance(push_data, dict):
                        push_iden = push_data.get('iden')
                        # 重複チェック
                        if push_iden and push_iden not in self.processed_push_idens:
                            self.processed_push_idens.add(push_iden)
                            self.logger.info(f"プッシュメッセージを受信: {push_data.get('title', 'N/A')}")
                            await self.on_push(push_data)
                            # 最後の処理時刻を更新
                            modified = push_data.get('modified', 0)
                            if modified > self.last_push_time:
                                self.last_push_time = modified
                        else:
                            self.logger.debug(f"重複pushをスキップ: {push_iden}")
                    else:
                        self.logger.debug(f"無効なプッシュデータ: {data}")
                
                # その他のメッセージ
                elif self.on_push and message_type not in ["nop", "tickle", None]:
                    self.logger.debug(f"その他のメッセージを受信: {message_type}")
                    if data and isinstance(data, dict):
                        # idenがある場合は重複チェック
                        data_iden = data.get('iden')
                        if data_iden and data_iden not in self.processed_push_idens:
                            self.processed_push_idens.add(data_iden)
                            await self.on_push(data)
                        elif not data_iden:
                            # idenがないメッセージは処理
                            await self.on_push(data)
                    
            except asyncio.TimeoutError:
                # タイムアウトチェック
                elapsed = (datetime.now(timezone.utc) - last_nop_time).total_seconds()
                if elapsed > self.NOP_TIMEOUT:
                    self.logger.warning(f"nopメッセージが{elapsed:.0f}秒間受信されていません")
                    # 接続をリセット
                    break
                else:
                    self.logger.debug(f"タイムアウト（正常） - 最後のnopから{elapsed:.0f}秒経過")
                    continue
            
            except json.JSONDecodeError as e:
                self.logger.error(f"JSONデコードエラー: {e}")
                continue
            
            except ConnectionClosedError as e:
                self.logger.warning(f"WebSocket接続がクローズされました: {e}")
                break
            except Exception as e:
                self.logger.error(f"メッセージ処理エラー: {e}")
                if not self.running:
                    break
                # 接続が切れた可能性があるため再接続
                error_str = str(e).lower()
                if "keepalive ping timeout" in error_str or "connection closed" in error_str:
                    self.logger.info("接続エラーのため再接続します")
                    break
                # 空のエラーメッセージや予期しないエラーも再接続
                if not error_str or error_str == "":
                    self.logger.warning("不明なエラーのため再接続します")
                    break
                # その他のエラーは継続（ただし連続エラーを防ぐため少し待機）
                await asyncio.sleep(0.1)
                continue
    
    async def _handle_tickle(self):
        """tickleメッセージを処理（実際のプッシュデータを取得）"""
        try:
            # 最後の処理時刻以降のプッシュを取得
            pushes = await self.pb_client.get_pushes(
                modified_after=self.last_push_time,
                limit=10
            )
            
            self.logger.debug(f"取得したプッシュ数: {len(pushes)}")
            
            for push in pushes:
                push_iden = push.get('iden')
                # 重複チェック
                if push_iden in self.processed_push_idens:
                    self.logger.debug(f"tickleで重複pushをスキップ: {push_iden}")
                    continue
                
                # アクティブで未読のプッシュのみ処理
                if (push.get("active", True) and 
                    not push.get("dismissed", False)):
                    
                    if push_iden:
                        self.processed_push_idens.add(push_iden)
                    
                    self.logger.info(f"プッシュを処理: {push.get('title', 'N/A')}")
                    
                    if self.on_push:
                        await self.on_push(push)
                    
                    # 最後の処理時刻を更新
                    modified = push.get("modified", 0)
                    if modified > self.last_push_time:
                        self.last_push_time = modified
        
        except Exception as e:
            self.logger.error(f"プッシュ取得エラー: {e}")
    
    async def run(self):
        """リスナーを実行"""
        try:
            self.logger.info("Pushbulletリスナーを開始します")
            await self.listen()
        except KeyboardInterrupt:
            self.logger.info("キーボード割り込みによる停止")
        except Exception as e:
            self.logger.error(f"リスナーエラー: {e}")
        finally:
            await self.disconnect()
            self.logger.info("Pushbulletリスナーを終了しました")


# テスト用のヘルパー関数
async def test_listener_with_logging():
    """ロギング付きでリスナーをテスト"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv("PUSHBULLET_TOKEN")
    
    if not api_key:
        print("PUSHBULLET_TOKEN環境変数が設定されていません")
        return
    
    async def on_push_handler(push):
        """プッシュハンドラー"""
        print(f"\n=== プッシュ受信 ===")
        print(f"タイプ: {push.get('type', 'N/A')}")
        print(f"タイトル: {push.get('title', 'N/A')}")
        print(f"本文: {push.get('body', 'N/A')}")
        print(f"送信者: {push.get('sender_name', 'N/A')}")
        print(f"デバイス宛先: {push.get('target_device_iden', '全デバイス')}")
        print("==================\n")
    
    # デバッグモードでリスナーを起動
    listener = AsyncPushbulletListener(api_key, on_push_handler, debug=True)
    
    try:
        await listener.run()
    except KeyboardInterrupt:
        print("\n停止します...")


if __name__ == "__main__":
    # テスト実行
    import asyncio
    asyncio.run(test_listener_with_logging())