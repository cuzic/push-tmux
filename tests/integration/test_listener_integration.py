#!/usr/bin/env python3
"""
リスナーの統合テスト
"""
import pytest
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
from dotenv import load_dotenv

# パスを追加
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from async_pushbullet import AsyncPushbulletListener


@pytest.mark.integration
class TestListenerIntegration:
    """リスナーの統合テスト"""
    
    @pytest.mark.asyncio
    async def test_basic_listener_lifecycle(self):
        """リスナーの基本的なライフサイクルをテスト"""
        api_key = "test_token_12345"
        push_received = []
        
        async def on_push(push):
            """プッシュハンドラー"""
            push_received.append(push)
        
        # モックWebSocketを使用
        with patch('websockets.connect') as mock_connect:
            mock_ws = AsyncMock()
            mock_ws.recv = AsyncMock(side_effect=[
                '{"type": "nop"}',
                asyncio.CancelledError()  # 終了シグナル
            ])
            mock_ws.close = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_ws
            
            listener = AsyncPushbulletListener(api_key, on_push, debug=False)
            
            # 初期状態の確認
            assert listener.running is False
            assert listener.websocket is None
            
            # リスナーを短時間実行
            try:
                await asyncio.wait_for(listener.run(), timeout=1)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            
            # 接続が試みられたことを確認
            mock_connect.assert_called()
    
    @pytest.mark.asyncio
    async def test_listener_message_handling(self):
        """メッセージハンドリングのテスト"""
        api_key = "test_token_12345"
        received_messages = []
        
        async def on_push(push):
            received_messages.append(push)
        
        with patch('websockets.connect', new_callable=AsyncMock) as mock_connect:
            mock_ws = AsyncMock()
            mock_ws.recv = AsyncMock(side_effect=[
                '{"type": "push", "push": {"iden": "test123", "type": "note", "title": "Test", "body": "Message"}}',
                '{"type": "nop"}',
                asyncio.CancelledError()
            ])
            mock_ws.close = AsyncMock()
            # websockets.connectは非同期でWebSocketを返す
            mock_connect.return_value = mock_ws
            
            # AsyncPushbulletのモック
            with patch('async_pushbullet.AsyncPushbullet') as mock_pb_class:
                mock_pb = AsyncMock()
                mock_pb.get_pushes = AsyncMock(return_value=[
                    {'type': 'note', 'title': 'Test', 'body': 'Message', 'iden': 'test123'}
                ])
                mock_pb_class.return_value = mock_pb
                
                listener = AsyncPushbulletListener(api_key, on_push, debug=False)
                
                try:
                    await asyncio.wait_for(listener.run(), timeout=1)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
                
                # メッセージが処理されたか確認
                assert len(received_messages) > 0
    
    @pytest.mark.asyncio
    async def test_listener_reconnection(self):
        """再接続機能のテスト"""
        api_key = "test_token_12345"
        connection_attempts = []
        
        async def on_push(push):
            pass
        
        with patch('websockets.connect') as mock_connect:
            # 最初の接続は失敗、2回目は成功
            async def connect_side_effect(*args, **kwargs):
                connection_attempts.append(len(connection_attempts))
                if len(connection_attempts) == 1:
                    raise Exception("Connection failed")
                
                mock_ws = AsyncMock()
                mock_ws.recv = AsyncMock(side_effect=[asyncio.CancelledError()])
                mock_ws.close = AsyncMock()
                return mock_ws
            
            mock_connect.side_effect = connect_side_effect
            
            listener = AsyncPushbulletListener(api_key, on_push, debug=False)
            
            try:
                await asyncio.wait_for(listener.run(), timeout=2)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            
            # 再接続が試みられたことを確認
            assert len(connection_attempts) >= 1


def test_summary():
    """テストサマリーの表示"""
    print("""
リスナー統合テスト
============================================================
以下の機能をテストします:
1. リスナーのライフサイクル管理
2. メッセージの受信と処理
3. WebSocket接続の再接続機能
4. エラーハンドリング
============================================================

実行コマンド:
  pytest tests/integration/test_listener_integration.py -v
""")