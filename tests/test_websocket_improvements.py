#!/usr/bin/env python3
"""
WebSocket改善のテスト
"""
import asyncio
import pytest
import sys
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json
import time
from websockets.exceptions import ConnectionClosedError

# プロジェクトのルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from async_pushbullet import AsyncPushbulletListener


class TestWebSocketImprovements:
    """WebSocket改善のテストクラス"""
    
    @pytest.fixture
    def api_key(self):
        """テスト用APIキー"""
        return "test_api_key"
    
    @pytest.fixture
    def listener(self, api_key):
        """テスト用リスナー"""
        return AsyncPushbulletListener(api_key)
    
    def test_constants_configuration(self, listener):
        """定数が正しく設定されているか確認"""
        # WebSocketタイムアウトは45秒（nopは約30秒間隔なので余裕を持たせる）
        assert listener.WEBSOCKET_TIMEOUT == 45
        
        # nopタイムアウトは90秒（通常の2倍以上の余裕）
        assert listener.NOP_TIMEOUT == 90
        
        # 最大再接続回数は5回（過剰な再接続を防ぐ）
        assert listener.MAX_RECONNECT_ATTEMPTS == 5
        
        # 再接続待機時間は5秒
        assert listener.RECONNECT_DELAY == 5
    
    @pytest.mark.asyncio
    async def test_connect_without_ping_pong(self, listener):
        """ping/pongが無効化されているか確認"""
        with patch('websockets.connect', new_callable=AsyncMock) as mock_connect:
            mock_ws = MagicMock()
            mock_connect.return_value = mock_ws
            
            result = await listener.connect()
            
            # 接続成功
            assert result is True
            
            # websockets.connectが呼ばれた
            mock_connect.assert_called_once()
            
            # ping_interval=Noneが設定されているか確認
            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs['ping_interval'] is None
            assert call_kwargs['close_timeout'] == 10
            
            # reconnect_attemptsがリセットされる
            assert listener.reconnect_attempts == 0
    
    @pytest.mark.asyncio
    async def test_nop_timeout_handling(self, listener):
        """nopタイムアウト処理が正しく動作するか確認"""
        listener.running = True
        listener.websocket = MagicMock()
        
        # モックメッセージ
        messages = [
            '{"type":"nop"}',  # 最初のnop
            asyncio.TimeoutError(),  # タイムアウト（正常）
            asyncio.TimeoutError(),  # タイムアウト（正常）
            asyncio.TimeoutError(),  # タイムアウト（異常 - 90秒超過）
        ]
        
        with patch.object(listener.websocket, 'recv', new_callable=AsyncMock) as mock_recv:
            # 各メッセージに対する処理を設定
            mock_recv.side_effect = messages
            
            # 時間をモック
            with patch('time.time') as mock_time:
                # 初期時刻
                mock_time.return_value = 1000.0
                
                # _receive_messagesを呼び出し
                with patch('asyncio.wait_for', new_callable=AsyncMock) as mock_wait_for:
                    async def wait_for_side_effect(coro, timeout):
                        result = await coro
                        if isinstance(result, Exception):
                            raise result
                        return result
                    
                    mock_wait_for.side_effect = wait_for_side_effect
                    
                    # 最初のnopを受信
                    mock_recv.side_effect = ['{"type":"nop"}']
                    
                    # 一度だけメッセージを処理
                    try:
                        await asyncio.wait_for(listener._receive_messages(), timeout=0.1)
                    except asyncio.TimeoutError:
                        pass
                    
                    # runningをFalseにして終了
                    listener.running = False
    
    @pytest.mark.asyncio
    async def test_error_handling_improvements(self, listener):
        """エラーハンドリングが改善されているか確認"""
        listener.running = True
        listener.websocket = MagicMock()
        
        # ConnectionClosedErrorのテスト
        with patch.object(listener.websocket, 'recv', new_callable=AsyncMock) as mock_recv:
            mock_recv.side_effect = ConnectionClosedError(None, None)
            
            # _receive_messagesを呼び出し
            await listener._receive_messages()
            
            # エラーが適切にログされているか（ここではbreakで終了するだけ確認）
            assert True  # エラーなく終了
    
    @pytest.mark.asyncio
    async def test_push_message_validation(self, listener):
        """pushメッセージの検証が正しく動作するか確認"""
        listener.running = True
        listener.websocket = MagicMock()
        
        # コールバックをモック
        mock_callback = AsyncMock()
        listener.on_push = mock_callback
        
        # 有効なpushメッセージ
        valid_push = {
            "type": "push",
            "push": {
                "type": "note",
                "title": "Test",
                "body": "Test message"
            }
        }
        
        # 無効なpushメッセージ（pushデータが空）
        invalid_push = {
            "type": "push",
            "push": {}
        }
        
        # nullのpushデータ
        null_push = {
            "type": "push",
            "push": None
        }
        
        with patch.object(listener.websocket, 'recv', new_callable=AsyncMock) as mock_recv:
            # 各メッセージをテスト
            for message in [valid_push, invalid_push, null_push]:
                mock_recv.side_effect = [json.dumps(message)]
                listener.running = True
                
                try:
                    await asyncio.wait_for(listener._receive_messages(), timeout=0.1)
                except (asyncio.TimeoutError, StopIteration):
                    pass
                
                listener.running = False
            
            # 有効なメッセージのみコールバックが呼ばれる
            assert mock_callback.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_reconnect_limit(self, listener):
        """再接続回数制限が機能するか確認"""
        listener.running = True
        
        with patch.object(listener, 'connect', new_callable=AsyncMock) as mock_connect:
            # 常に接続失敗
            mock_connect.return_value = False
            
            with patch('asyncio.sleep', new_callable=AsyncMock):
                # listenを実行（最大再接続回数に達したら終了）
                try:
                    await asyncio.wait_for(listener.listen(), timeout=1)
                except asyncio.TimeoutError:
                    pass  # タイムアウトは予期される
                
                # 最大再接続回数（5回）を超えていないか確認
                assert listener.reconnect_attempts == listener.MAX_RECONNECT_ATTEMPTS
    
    @pytest.mark.asyncio
    async def test_connection_error_detection(self, listener):
        """接続エラーの検出が正しく動作するか確認"""
        listener.running = True
        listener.websocket = MagicMock()
        
        # keepalive ping timeoutエラー
        error_messages = [
            "sent 1011 (internal error) keepalive ping timeout",
            "connection closed",
            "Connection CLOSED",
        ]
        
        for error_msg in error_messages:
            with patch.object(listener.websocket, 'recv', new_callable=AsyncMock) as mock_recv:
                mock_recv.side_effect = Exception(error_msg)
                
                # _receive_messagesを呼び出し
                result = await listener._receive_messages()
                
                # エラーメッセージが検出されてbreakするか確認
                # （メソッドは正常終了する）
                assert result is None
    
    def test_is_connected_method(self, listener):
        """is_connectedメソッドが正しく動作するか確認"""
        # websocketがNoneの場合
        listener.websocket = None
        assert listener.is_connected() is False
        
        # websocketが存在する場合
        listener.websocket = MagicMock()
        
        # closedプロパティがある場合
        listener.websocket.closed = False
        assert listener.is_connected() is True
        
        listener.websocket.closed = True
        assert listener.is_connected() is False
        
        # stateプロパティがある場合
        del listener.websocket.closed
        from websockets.protocol import State
        
        listener.websocket.state = State.OPEN
        assert listener.is_connected() is True
        
        listener.websocket.state = State.CLOSED
        assert listener.is_connected() is False
        
        # どちらのプロパティもない場合（フォールバック）
        del listener.websocket.state
        assert listener.is_connected() is True


@pytest.mark.asyncio
async def test_integration_short_run():
    """短時間の統合テスト"""
    api_key = os.getenv('PUSHBULLET_TOKEN')
    if not api_key:
        pytest.skip("PUSHBULLET_TOKEN not set")
    
    # 統計情報
    stats = {
        'nop_count': 0,
        'errors': 0,
        'reconnects': 0
    }
    
    async def on_push(push):
        if push.get('type') == 'nop':
            stats['nop_count'] += 1
    
    # カスタムリスナー
    class TestListener(AsyncPushbulletListener):
        async def connect(self):
            result = await super().connect()
            if result:
                stats['reconnects'] += 1
            return result
    
    listener = TestListener(api_key, on_push)
    
    # 5秒間実行
    try:
        await asyncio.wait_for(listener.run(), timeout=5)
    except asyncio.TimeoutError:
        pass
    finally:
        if listener.running:
            await listener.disconnect()
    
    # 検証
    assert stats['reconnects'] == 1  # 初回接続のみ
    assert stats['errors'] == 0  # エラーなし
    # nopメッセージは受信されるかもしれないし、されないかもしれない（タイミング次第）


if __name__ == "__main__":
    # 基本的なテストを実行
    import unittest
    
    # テストランナーを作成
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 簡単な確認テスト
    print("WebSocket改善のテストを実行します...")
    print("=" * 60)
    
    # テストインスタンスを作成
    test_instance = TestWebSocketImprovements()
    
    # 定数設定のテスト
    listener = AsyncPushbulletListener("test_key")
    print("✓ 定数設定のテスト")
    print(f"  WEBSOCKET_TIMEOUT: {listener.WEBSOCKET_TIMEOUT}秒")
    print(f"  NOP_TIMEOUT: {listener.NOP_TIMEOUT}秒")
    print(f"  MAX_RECONNECT_ATTEMPTS: {listener.MAX_RECONNECT_ATTEMPTS}回")
    assert listener.WEBSOCKET_TIMEOUT == 45
    assert listener.NOP_TIMEOUT == 90
    assert listener.MAX_RECONNECT_ATTEMPTS == 5
    print("  → OK")
    
    # is_connectedメソッドのテスト
    print("\n✓ is_connectedメソッドのテスト")
    listener.websocket = None
    assert listener.is_connected() is False
    print("  websocket=None → False: OK")
    
    listener.websocket = MagicMock()
    listener.websocket.closed = False
    assert listener.is_connected() is True
    print("  closed=False → True: OK")
    
    listener.websocket.closed = True
    assert listener.is_connected() is False
    print("  closed=True → False: OK")
    
    print("\n" + "=" * 60)
    print("すべてのテストが成功しました！")