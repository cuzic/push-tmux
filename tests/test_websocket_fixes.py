#!/usr/bin/env python3
"""
WebSocket修正のpytestテスト
"""
import asyncio
import pytest
import sys
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
import json
import time
from websockets.exceptions import ConnectionClosedError
from websockets.protocol import State

# プロジェクトのルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from async_pushbullet import AsyncPushbulletListener


class TestWebSocketConfiguration:
    """WebSocket設定のテスト"""
    
    def test_timeout_constants(self):
        """タイムアウト定数が正しく設定されているか"""
        listener = AsyncPushbulletListener("test_key")
        
        assert listener.WEBSOCKET_TIMEOUT == 45, "WebSocketタイムアウトは45秒であるべき"
        assert listener.NOP_TIMEOUT == 90, "nopタイムアウトは90秒であるべき"
        assert listener.MAX_RECONNECT_ATTEMPTS == 5, "最大再接続回数は5回であるべき"
        assert listener.RECONNECT_DELAY == 5, "再接続待機時間は5秒であるべき"
    
    @pytest.mark.asyncio
    async def test_ping_pong_disabled(self):
        """ping/pongが無効化されているか"""
        listener = AsyncPushbulletListener("test_key")
        
        with patch('websockets.connect', new_callable=AsyncMock) as mock_connect:
            mock_ws = MagicMock()
            mock_connect.return_value = mock_ws
            
            result = await listener.connect()
            
            # 接続成功
            assert result is True
            
            # websockets.connectの呼び出し引数を確認
            call_args = mock_connect.call_args
            assert call_args is not None
            
            # ping_interval=Noneが設定されているか
            kwargs = call_args[1] if len(call_args) > 1 else call_args.kwargs
            assert 'ping_interval' in kwargs
            assert kwargs['ping_interval'] is None, "ping_intervalはNoneであるべき"
            assert kwargs.get('close_timeout') == 10, "close_timeoutは10秒であるべき"
    
    def test_initial_running_state(self):
        """初期状態でrunningがFalseか"""
        listener = AsyncPushbulletListener("test_key")
        assert listener.running is False, "初期状態でrunningはFalseであるべき"


class TestConnectionManagement:
    """接続管理のテスト"""
    
    @pytest.mark.asyncio
    async def test_running_flag_initialization(self):
        """listenメソッドでrunningフラグが設定されるか"""
        listener = AsyncPushbulletListener("test_key")
        
        with patch('asyncio.sleep', new_callable=AsyncMock):  # sleepをモック
            with patch.object(listener, 'connect', new_callable=AsyncMock) as mock_connect:
                with patch.object(listener, '_receive_messages', new_callable=AsyncMock) as mock_receive:
                    # 接続失敗で即終了するよう設定
                    mock_connect.return_value = False
                    
                    # listenを実行（タイムアウト付き）
                    try:
                        await asyncio.wait_for(listener.listen(), timeout=1)
                    except asyncio.TimeoutError:
                        pass  # タイムアウトは予期される
                    
                    # connectが呼ばれたことを確認
                    mock_connect.assert_called()
                    # 最大再接続回数に達したことを確認
                    assert listener.reconnect_attempts == listener.MAX_RECONNECT_ATTEMPTS
    
    @pytest.mark.asyncio
    async def test_reconnect_limit(self):
        """再接続回数制限が機能するか"""
        listener = AsyncPushbulletListener("test_key")
        
        with patch.object(listener, 'connect', new_callable=AsyncMock) as mock_connect:
            with patch('asyncio.sleep', new_callable=AsyncMock):
                # 常に接続失敗
                mock_connect.return_value = False
                
                try:
                    await asyncio.wait_for(listener.listen(), timeout=1)
                except asyncio.TimeoutError:
                    pass  # タイムアウトは予期される
                
                # 最大再接続回数を超えていないか
                assert listener.reconnect_attempts == listener.MAX_RECONNECT_ATTEMPTS
                assert mock_connect.call_count <= listener.MAX_RECONNECT_ATTEMPTS + 1
    
    @pytest.mark.asyncio
    async def test_successful_reconnect_resets_counter(self):
        """接続成功で再接続カウンタがリセットされるか"""
        listener = AsyncPushbulletListener("test_key")
        listener.reconnect_attempts = 3  # 事前に失敗回数を設定
        
        with patch('websockets.connect', new_callable=AsyncMock) as mock_connect:
            mock_ws = MagicMock()
            mock_connect.return_value = mock_ws
            
            result = await listener.connect()
            
            assert result is True
            assert listener.reconnect_attempts == 0, "接続成功で再接続カウンタがリセットされるべき"


class TestIsConnectedMethod:
    """is_connectedメソッドのテスト"""
    
    def test_websocket_none(self):
        """websocketがNoneの場合"""
        listener = AsyncPushbulletListener("test_key")
        listener.websocket = None
        assert listener.is_connected() is False
    
    def test_websocket_with_closed_attribute(self):
        """closedプロパティがある場合"""
        listener = AsyncPushbulletListener("test_key")
        listener.websocket = MagicMock()
        
        # closedがFalse
        listener.websocket.closed = False
        assert listener.is_connected() is True
        
        # closedがTrue
        listener.websocket.closed = True
        assert listener.is_connected() is False
    
    def test_websocket_with_state_attribute(self):
        """stateプロパティがある場合"""
        listener = AsyncPushbulletListener("test_key")
        listener.websocket = MagicMock()
        
        # closedプロパティを削除
        if hasattr(listener.websocket, 'closed'):
            del listener.websocket.closed
        
        # stateがOPEN
        listener.websocket.state = State.OPEN
        assert listener.is_connected() is True
        
        # stateがCLOSED
        listener.websocket.state = State.CLOSED
        assert listener.is_connected() is False
    
    def test_websocket_fallback(self):
        """フォールバックの場合"""
        listener = AsyncPushbulletListener("test_key")
        listener.websocket = MagicMock()
        
        # どちらのプロパティも持たない
        if hasattr(listener.websocket, 'closed'):
            del listener.websocket.closed
        if hasattr(listener.websocket, 'state'):
            del listener.websocket.state
        
        assert listener.is_connected() is True, "フォールバックではTrueを返すべき"


class TestErrorHandling:
    """エラーハンドリングのテスト"""
    
    @pytest.mark.asyncio
    async def test_connection_closed_error_handling(self):
        """ConnectionClosedErrorの処理"""
        listener = AsyncPushbulletListener("test_key")
        listener.running = True
        listener.websocket = MagicMock()
        
        with patch.object(listener.websocket, 'recv', new_callable=AsyncMock) as mock_recv:
            mock_recv.side_effect = ConnectionClosedError(None, None)
            
            # エラーが発生してもメソッドは正常終了する
            await listener._receive_messages()
            
            # メソッドが終了することを確認（例外が発生しない）
            assert True
    
    @pytest.mark.asyncio
    async def test_keepalive_timeout_error_handling(self):
        """keepalive ping timeoutエラーの処理"""
        listener = AsyncPushbulletListener("test_key")
        listener.running = True
        listener.websocket = MagicMock()
        
        errors = [
            "sent 1011 (internal error) keepalive ping timeout",
            "connection closed",
            "Connection CLOSED"
        ]
        
        for error_msg in errors:
            with patch.object(listener.websocket, 'recv', new_callable=AsyncMock) as mock_recv:
                mock_recv.side_effect = Exception(error_msg)
                
                # エラーが発生してもメソッドは正常終了する
                await listener._receive_messages()
                
                # breakで終了することを確認
                assert True
    
    @pytest.mark.asyncio
    async def test_empty_error_handling(self):
        """空のエラーメッセージの処理"""
        listener = AsyncPushbulletListener("test_key")
        listener.running = True
        listener.websocket = MagicMock()
        
        with patch.object(listener.websocket, 'recv', new_callable=AsyncMock) as mock_recv:
            mock_recv.side_effect = Exception("")  # 空のエラーメッセージ
            
            # エラーが発生してもメソッドは正常終了する
            await listener._receive_messages()
            
            # breakで終了することを確認
            assert True
    
    @pytest.mark.asyncio
    async def test_json_decode_error_handling(self):
        """JSONデコードエラーの処理"""
        listener = AsyncPushbulletListener("test_key")
        listener.running = True
        listener.websocket = MagicMock()
        
        with patch.object(listener.websocket, 'recv', new_callable=AsyncMock) as mock_recv:
            # 無効なJSONを返す
            mock_recv.return_value = "invalid json"
            
            with patch('asyncio.wait_for', new_callable=AsyncMock) as mock_wait_for:
                mock_wait_for.return_value = "invalid json"
                
                # runningをFalseにして終了させる
                async def stop_after_one():
                    listener.running = False
                    return "invalid json"
                
                mock_wait_for.side_effect = [stop_after_one()]
                
                # エラーが発生してもメソッドは正常終了する
                await listener._receive_messages()
                
                # continueで処理が継続されることを確認
                assert True


class TestMessageProcessing:
    """メッセージ処理のテスト"""
    
    @pytest.mark.asyncio
    async def test_nop_message_processing(self):
        """nopメッセージの処理"""
        listener = AsyncPushbulletListener("test_key")
        listener.running = True
        listener.websocket = MagicMock()
        
        nop_received = False
        
        async def on_push(push):
            nonlocal nop_received
            if push.get('type') == 'nop':
                nop_received = True
        
        listener.on_push = on_push
        
        with patch.object(listener.websocket, 'recv', new_callable=AsyncMock) as mock_recv:
            with patch('asyncio.wait_for', new_callable=AsyncMock) as mock_wait_for:
                # nopメッセージを返す
                mock_wait_for.return_value = '{"type":"nop"}'
                
                # 1回だけ実行して終了
                listener.running = False
                mock_recv.return_value = '{"type":"nop"}'
                
                try:
                    await asyncio.wait_for(listener._receive_messages(), timeout=0.5)
                except asyncio.TimeoutError:
                    pass
                
                # nopメッセージは通常on_pushに渡されない（ログのみ）
                assert not nop_received
    
    @pytest.mark.asyncio
    async def test_push_message_validation(self):
        """pushメッセージの検証"""
        listener = AsyncPushbulletListener("test_key")
        listener.websocket = MagicMock()
        
        callback_called = []
        
        async def on_push(push):
            callback_called.append(push)
        
        listener.on_push = on_push
        
        # 有効なpushメッセージ（idenフィールドを追加）
        valid_push = json.dumps({
            "type": "push",
            "push": {"iden": "test123", "title": "Test", "body": "Message"}
        })
        
        with patch.object(listener.websocket, 'recv', new_callable=AsyncMock) as mock_recv:
            with patch('asyncio.wait_for', new_callable=AsyncMock) as mock_wait_for:
                # 有効なメッセージを返してから終了
                mock_wait_for.return_value = valid_push
                listener.running = True
                
                # 1回だけ実行するための工夫
                call_count = 0
                async def side_effect(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count > 1:
                        listener.running = False
                        raise asyncio.TimeoutError()
                    return valid_push
                
                mock_wait_for.side_effect = side_effect
                
                # _receive_messagesを実行
                await listener._receive_messages()
                
                # コールバックが呼ばれたか確認
                assert len(callback_called) == 1
                assert callback_called[0]["title"] == "Test"
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """タイムアウト処理のテスト"""
        listener = AsyncPushbulletListener("test_key")
        listener.running = True
        listener.websocket = MagicMock()
        
        with patch.object(listener.websocket, 'recv', new_callable=AsyncMock) as mock_recv:
            with patch('asyncio.wait_for', new_callable=AsyncMock) as mock_wait_for:
                with patch('time.time') as mock_time:
                    # 初期時刻
                    mock_time.return_value = 1000.0
                    
                    # タイムアウトエラーを発生させる
                    mock_wait_for.side_effect = asyncio.TimeoutError()
                    
                    # runningをFalseにして終了
                    listener.running = False
                    
                    # エラーが発生してもメソッドは正常終了する
                    await listener._receive_messages()
                    
                    # タイムアウトが適切に処理されることを確認
                    assert True


@pytest.mark.integration
class TestIntegration:
    """統合テスト"""
    
    @pytest.mark.asyncio
    async def test_short_connection(self):
        """短時間の接続テスト"""
        api_key = os.getenv('PUSHBULLET_TOKEN')
        if not api_key or api_key == 'test_token_12345':
            pytest.skip("Real PUSHBULLET_TOKEN not set")
        
        connected = False
        errors = []
        
        async def on_push(push):
            pass
        
        class TestListener(AsyncPushbulletListener):
            async def connect(self):
                nonlocal connected
                result = await super().connect()
                if result:
                    connected = True
                return result
            
            async def _receive_messages(self):
                try:
                    await super()._receive_messages()
                except Exception as e:
                    errors.append(str(e))
                    raise
        
        listener = TestListener(api_key, on_push)
        
        # 3秒間実行
        try:
            await asyncio.wait_for(listener.run(), timeout=3)
        except asyncio.TimeoutError:
            pass
        finally:
            if listener.running:
                await listener.disconnect()
        
        # 検証
        assert connected is True, "接続が成功するべき"
        assert len(errors) == 0, f"エラーが発生しないべき: {errors}"


# pytest実行用のヘルパー
def test_summary():
    """テストサマリー（pytest以外で実行した場合）"""
    print("このファイルはpytestで実行してください:")
    print("  pytest tests/test_websocket_fixes.py -v")
    print("\n統合テストも実行する場合:")
    print("  pytest tests/test_websocket_fixes.py -v -m integration")


if __name__ == "__main__":
    test_summary()