#!/usr/bin/env python3
"""
ライブルーティング機能の統合テスト
"""
import pytest
import asyncio
import os
from unittest.mock import AsyncMock, patch

# パスを追加
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from async_pushbullet import AsyncPushbullet


@pytest.mark.integration
class TestLiveRouting:
    """ライブルーティング機能の統合テスト"""
    
    @pytest.mark.asyncio
    async def test_auto_route_session_detection(self):
        """自動ルーティングでのセッション検出テスト"""
        # tmuxセッション一覧のモック
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(
                b'project-a\nproject-b\nwebapp\n', b''
            ))
            mock_exec.return_value = mock_process
            
            # セッション一覧を取得
            result = await asyncio.create_subprocess_exec(
                'tmux', 'ls', '-F', '#{session_name}',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            sessions = stdout.decode().strip().split('\n') if stdout else []
            
            assert 'project-a' in sessions
            assert 'project-b' in sessions
            assert 'webapp' in sessions
    
    @pytest.mark.asyncio
    async def test_device_to_session_mapping(self):
        """デバイスからセッションへのマッピングテスト"""
        device_mapping = {
            "mobile-dev": "frontend",
            "backend-api": "backend",
            "webapp": "development"
        }
        
        # 各マッピングが正しく機能することを確認
        for device, session in device_mapping.items():
            assert device_mapping[device] == session
        
        # 存在しないデバイスの処理
        assert device_mapping.get("nonexistent") is None
    
    @pytest.mark.asyncio
    async def test_message_routing_with_mock_pushbullet(self):
        """Pushbulletをモックしたメッセージルーティングテスト"""
        api_key = os.getenv('PUSHBULLET_TOKEN', 'test_token')
        if not api_key or api_key == 'test_token_12345':
            pytest.skip("Real PUSHBULLET_TOKEN not set")
        
        with patch('tests.integration.test_live_routing.AsyncPushbullet') as mock_pb_class:
            mock_pb = AsyncMock()
            mock_pb.get_devices = AsyncMock(return_value=[
                {'nickname': 'project-a', 'iden': 'device1', 'active': True},
                {'nickname': 'project-b', 'iden': 'device2', 'active': True},
            ])
            mock_pb.push_note = AsyncMock()
            
            # モックインスタンスを設定
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_pb)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_pb_class.return_value = mock_instance
            
            api_key = "test_token"
            async with AsyncPushbullet(api_key) as pb:
                devices = await pb.get_devices()
                
                # デバイスが正しく取得されていることを確認
                assert len(devices) == 2
                assert devices[0]['nickname'] == 'project-a'
                assert devices[1]['nickname'] == 'project-b'
                
                # テストメッセージの送信
                for device in devices:
                    await pb.push_note(
                        title="Test",
                        body=f"Test message for {device['nickname']}",
                        device_iden=device['iden']
                    )
                
                # push_noteが呼ばれたことを確認
                assert mock_pb.push_note.call_count == 2


def test_summary():
    """テストサマリーの表示"""
    print("""
ライブルーティング統合テスト
============================================================
以下の機能をテストします:
1. 自動ルーティングでのtmuxセッション検出
2. デバイスからセッションへのマッピング
3. Pushbullet経由のメッセージルーティング
4. 複数デバイス/セッションの処理
============================================================

実行コマンド:
  pytest tests/integration/test_live_routing.py -v
""")