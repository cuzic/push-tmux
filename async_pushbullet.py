"""
非同期Pushbulletクライアント実装
"""
import asyncio
import json
import time
from typing import Optional, Dict, List, Any, Callable
import aiohttp
import websockets


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
    """非同期Pushbulletリスナー（WebSocket）"""
    
    def __init__(self, api_key: str, on_push: Optional[Callable] = None):
        self.api_key = api_key
        self.on_push = on_push
        self.ws_url = f"wss://stream.pushbullet.com/websocket/{api_key}"
        self.websocket = None
        self.running = False
        self.pb_client = AsyncPushbullet(api_key)
        self.last_push_time = time.time()
    
    async def connect(self):
        """WebSocketに接続"""
        self.websocket = await websockets.connect(self.ws_url)
        self.running = True
        print("WebSocketに接続しました")
    
    async def disconnect(self):
        """WebSocketを切断"""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            print("WebSocketを切断しました")
        await self.pb_client.close()
    
    async def listen(self):
        """メッセージを待ち受ける"""
        try:
            await self.connect()
            
            while self.running:
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(), 
                        timeout=30
                    )
                    
                    data = json.loads(message)
                    
                    # nop（キープアライブ）は無視
                    if data.get("type") == "nop":
                        continue
                    
                    # tickleメッセージの場合、実際のプッシュを取得
                    if data.get("type") == "tickle" and data.get("subtype") == "push":
                        await self._handle_tickle()
                    
                    # その他のメッセージも処理
                    elif self.on_push and data.get("type") != "nop":
                        await self.on_push(data)
                        
                except asyncio.TimeoutError:
                    # タイムアウトは正常（キープアライブ）
                    continue
                except websockets.exceptions.ConnectionClosed:
                    print("WebSocket接続が切断されました")
                    break
                except Exception as e:
                    print(f"エラー: {e}")
                    if not self.running:
                        break
                    # 再接続を試みる
                    await asyncio.sleep(5)
                    await self.connect()
        
        finally:
            await self.disconnect()
    
    async def _handle_tickle(self):
        """tickleメッセージを処理（実際のプッシュデータを取得）"""
        try:
            # 最後の処理時刻以降のプッシュを取得
            pushes = await self.pb_client.get_pushes(
                modified_after=self.last_push_time,
                limit=10
            )
            
            for push in pushes:
                # noteタイプで、アクティブで、dismissedでないもののみ処理
                if (push.get("type") == "note" and 
                    push.get("active", True) and 
                    not push.get("dismissed", False)):
                    
                    if self.on_push:
                        await self.on_push(push)
                    
                    # 最後の処理時刻を更新
                    if push.get("modified", 0) > self.last_push_time:
                        self.last_push_time = push.get("modified", time.time())
        
        except Exception as e:
            print(f"プッシュ取得エラー: {e}")
    
    async def run(self):
        """リスナーを実行"""
        try:
            await self.listen()
        except KeyboardInterrupt:
            print("\n停止します...")
        finally:
            await self.disconnect()


async def test_async_pushbullet():
    """テスト関数"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv("PUSHBULLET_TOKEN")
    
    if not api_key:
        print("PUSHBULLET_TOKEN環境変数が設定されていません")
        return
    
    async with AsyncPushbullet(api_key) as pb:
        # ユーザー情報取得
        user = await pb.get_user()
        print(f"ユーザー: {user.get('email')}")
        
        # デバイス一覧取得
        devices = await pb.get_devices()
        print(f"デバイス数: {len(devices)}")
        for device in devices:
            print(f"  - {device['nickname']} ({device['iden']})")
        
        # テストプッシュ送信
        push = await pb.push_note("AsyncPushbulletテスト", "非同期実装のテスト")
        print(f"プッシュ送信: {push.get('iden')}")


if __name__ == "__main__":
    # テスト実行
    asyncio.run(test_async_pushbullet())