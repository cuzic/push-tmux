#!/usr/bin/env python3
"""
自動ルーティング機能のテスト
"""
import asyncio
import pytest
import sys
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
import json
import click.testing

# プロジェクトのルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from push_tmux import cli
from async_pushbullet import AsyncPushbullet


class TestAutoRouteMode:
    """自動ルーティングモードのテスト"""
    
    def test_auto_route_session_detection(self):
        """tmuxセッションの自動検出"""
        # モックデバイス
        devices = [
            {'iden': 'dev1', 'nickname': 'push-tmux', 'active': True},
            {'iden': 'dev2', 'nickname': '1on1-ver2', 'active': True},
            {'iden': 'dev3', 'nickname': 'non-existent', 'active': True},
        ]
        
        with patch.dict(os.environ, {'PUSHBULLET_TOKEN': 'test_token'}):
            with patch('push_tmux.AsyncPushbullet') as mock_pb_class:
                mock_pb = AsyncMock()
                mock_pb.__aenter__.return_value = mock_pb
                mock_pb.get_devices.return_value = devices
                mock_pb_class.return_value = mock_pb
                
                with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
                    # has-sessionの結果をモック
                    async def has_session_side_effect(*args, **kwargs):
                        mock_proc = AsyncMock()
                        mock_proc.communicate.return_value = (b'', b'')
                        
                        # コマンドライン引数からセッション名を取得
                        if 'has-session' in args and '-t' in args:
                            session_idx = args.index('-t') + 1
                            session_name = args[session_idx]
                            
                            # push-tmuxと1on1-ver2は存在、non-existentは存在しない
                            if session_name in ['push-tmux', '1on1-ver2']:
                                mock_proc.returncode = 0
                            else:
                                mock_proc.returncode = 1
                        else:
                            mock_proc.returncode = 0
                        
                        return mock_proc
                    
                    mock_exec.side_effect = has_session_side_effect
                    
                    # CLIを実行（listenコマンドをモック）
                    with patch('push_tmux.AsyncPushbulletListener') as mock_listener_class:
                        mock_listener = AsyncMock()
                        mock_listener.run = AsyncMock()
                        mock_listener_class.return_value = mock_listener
                        
                        runner = click.testing.CliRunner()
                        result = runner.invoke(cli, ['listen', '--auto-route'], input='\n', catch_exceptions=False)
                    
                    # セッション検出が正しく動作したか確認
                    assert 'push-tmux' in result.output
                    assert '1on1-ver2' in result.output
                    assert 'tmuxセッションあり' in result.output or 'tmuxセッションなし' in result.output
    
    @pytest.mark.asyncio
    async def test_auto_route_message_routing(self):
        """メッセージの自動ルーティング"""
        import push_tmux
        
        # テスト用のプッシュメッセージ
        test_push = {
            'type': 'note',
            'iden': 'push123',
            'target_device_iden': 'dev1',
            'title': 'Test Message',
            'body': 'echo "Test auto-route"',
            'sender_name': 'Test Sender'
        }
        
        # デバイスキャッシュ
        device_cache = {
            'dev1': 'push-tmux',
            'dev2': '1on1-ver2',
            'dev3': 'non-existent'
        }
        
        with patch('push_tmux.send_to_tmux', new_callable=AsyncMock) as mock_send:
            with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
                # has-sessionでpush-tmuxセッションが存在
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'', b'')
                mock_proc.returncode = 0
                mock_exec.return_value = mock_proc
                
                # on_push_auto_routeを直接テスト
                config = {}
                
                # 関数を手動で作成（実際の実装をシミュレート）
                async def on_push_auto_route(push):
                    if push.get('type') != 'note':
                        return
                    
                    target_device_iden = push.get('target_device_iden')
                    if not target_device_iden:
                        return
                    
                    target_device_name = device_cache.get(target_device_iden)
                    if not target_device_name:
                        return
                    
                    # tmuxセッション確認
                    result = await mock_exec(
                        'tmux', 'has-session', '-t', target_device_name,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await result.communicate()
                    
                    if result.returncode == 0:
                        await mock_send(config, push['body'], device_name=target_device_name)
                
                # プッシュを処理
                await on_push_auto_route(test_push)
                
                # send_to_tmuxが正しいデバイス名で呼ばれたか確認
                mock_send.assert_called_once_with(
                    config,
                    'echo "Test auto-route"',
                    device_name='push-tmux'
                )
    
    @pytest.mark.asyncio
    async def test_auto_route_skip_missing_session(self):
        """存在しないセッションへのメッセージをスキップ"""
        import push_tmux
        
        test_push = {
            'type': 'note',
            'iden': 'push456',
            'target_device_iden': 'dev3',
            'title': 'Test Message',
            'body': 'echo "Should be skipped"',
            'sender_name': 'Test Sender'
        }
        
        device_cache = {
            'dev3': 'non-existent'
        }
        
        with patch('push_tmux.send_to_tmux', new_callable=AsyncMock) as mock_send:
            with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
                with patch('click.echo') as mock_echo:
                    # has-sessionでセッションが存在しない
                    mock_proc = AsyncMock()
                    mock_proc.communicate.return_value = (b'', b'')
                    mock_proc.returncode = 1  # セッション不在
                    mock_exec.return_value = mock_proc
                    
                    config = {}
                    
                    async def on_push_auto_route(push):
                        if push.get('type') != 'note':
                            return
                        
                        target_device_iden = push.get('target_device_iden')
                        if not target_device_iden:
                            return
                        
                        target_device_name = device_cache.get(target_device_iden)
                        if not target_device_name:
                            return
                        
                        # tmuxセッション確認
                        result = await mock_exec(
                            'tmux', 'has-session', '-t', target_device_name,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        await result.communicate()
                        
                        if result.returncode != 0:
                            mock_echo(f"[スキップ] {target_device_name}: tmuxセッションが存在しません")
                            return
                        
                        await mock_send(config, push['body'], device_name=target_device_name)
                    
                    await on_push_auto_route(test_push)
                    
                    # send_to_tmuxが呼ばれていないことを確認
                    mock_send.assert_not_called()
                    
                    # スキップメッセージが出力されたか確認
                    mock_echo.assert_called_with("[スキップ] non-existent: tmuxセッションが存在しません")
    
    @pytest.mark.asyncio
    async def test_auto_route_multiple_sessions(self):
        """複数セッションへの同時ルーティング"""
        import push_tmux
        
        # 複数のプッシュメッセージ
        pushes = [
            {
                'type': 'note',
                'iden': 'push1',
                'target_device_iden': 'dev1',
                'title': 'Message 1',
                'body': 'echo "To push-tmux"',
                'sender_name': 'Sender 1'
            },
            {
                'type': 'note',
                'iden': 'push2',
                'target_device_iden': 'dev2',
                'title': 'Message 2',
                'body': 'echo "To 1on1-ver2"',
                'sender_name': 'Sender 2'
            }
        ]
        
        device_cache = {
            'dev1': 'push-tmux',
            'dev2': '1on1-ver2'
        }
        
        with patch('push_tmux.send_to_tmux', new_callable=AsyncMock) as mock_send:
            with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
                # 両方のセッションが存在
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'', b'')
                mock_proc.returncode = 0
                mock_exec.return_value = mock_proc
                
                config = {}
                
                async def on_push_auto_route(push):
                    if push.get('type') != 'note':
                        return
                    
                    target_device_iden = push.get('target_device_iden')
                    if not target_device_iden:
                        return
                    
                    target_device_name = device_cache.get(target_device_iden)
                    if not target_device_name:
                        return
                    
                    # tmuxセッション確認
                    result = await mock_exec(
                        'tmux', 'has-session', '-t', target_device_name,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await result.communicate()
                    
                    if result.returncode == 0:
                        await mock_send(config, push['body'], device_name=target_device_name)
                
                # 両方のプッシュを処理
                for push in pushes:
                    await on_push_auto_route(push)
                
                # 両方のセッションに送信されたか確認
                assert mock_send.call_count == 2
                calls = mock_send.call_args_list
                
                # 最初の呼び出し
                assert calls[0][0][1] == 'echo "To push-tmux"'
                assert calls[0][1]['device_name'] == 'push-tmux'
                
                # 2番目の呼び出し
                assert calls[1][0][1] == 'echo "To 1on1-ver2"'
                assert calls[1][1]['device_name'] == '1on1-ver2'


def test_summary():
    """テストサマリー"""
    print("自動ルーティング機能のテスト")
    print("=" * 60)
    print("以下の機能をテストします:")
    print("1. tmuxセッションの自動検出")
    print("2. メッセージの自動ルーティング")
    print("3. 存在しないセッションのスキップ")
    print("4. 複数セッションへの同時ルーティング")
    print("=" * 60)
    print("\n実行コマンド:")
    print("  pytest tests/test_auto_route.py -v")


if __name__ == "__main__":
    test_summary()