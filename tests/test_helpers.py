#!/usr/bin/env python3
"""
テスト用ヘルパー関数
"""
from unittest.mock import MagicMock, AsyncMock


def create_tmux_mock(existing_sessions=None, current_session='test-session', 
                     windows='0', panes='0'):
    """tmuxコマンドモックを作成するヘルパー関数
    
    Args:
        existing_sessions: 存在するセッションのリスト
        current_session: 現在のセッション名
        windows: list-windowsの結果（改行区切り文字列）
        panes: list-panesの結果（改行区切り文字列）
    """
    if existing_sessions is None:
        existing_sessions = []
    
    async def mock_exec(*args, **kwargs):
        if 'has-session' in args:
            result = MagicMock()
            # 指定されたセッションが存在するかチェック
            for session in existing_sessions:
                if session in args:
                    result.wait = AsyncMock(return_value=0)
                    result.returncode = 0
                    result.communicate = AsyncMock(return_value=(b'', b''))
                    return result
            # セッションが存在しない場合
            result.wait = AsyncMock(return_value=1)
            result.returncode = 1
            result.communicate = AsyncMock(return_value=(b'', b''))
            return result
        elif 'display-message' in args:
            result = MagicMock()
            result.returncode = 0
            result.communicate = AsyncMock(return_value=(f'{current_session}\n'.encode(), b''))
            return result
        elif 'list-windows' in args:
            result = MagicMock()
            result.communicate = AsyncMock(return_value=(f'{windows}\n'.encode(), b''))
            return result
        elif 'list-panes' in args:
            result = MagicMock()
            result.communicate = AsyncMock(return_value=(f'{panes}\n'.encode(), b''))
            return result
        else:
            # send-keysなど、他のコマンドの場合
            process = MagicMock()
            process.wait = AsyncMock(return_value=None)
            return process
    
    return mock_exec


def assert_send_keys_called(mock_subprocess, expected_target, expected_message):
    """send-keysコマンドが正しく呼ばれたことを確認
    
    Args:
        mock_subprocess: モックされたsubprocess
        expected_target: 期待されるtmuxターゲット（例: "session:0.0"）
        expected_message: 期待されるメッセージ
    """
    send_calls = [call for call in mock_subprocess.call_args_list 
                  if 'send-keys' in str(call)]
    assert len(send_calls) == 2, f"Expected 2 send-keys calls, got {len(send_calls)}"
    
    # メッセージ送信の確認
    message_call = send_calls[0]
    assert message_call[0][3] == expected_target, f"Expected target {expected_target}, got {message_call[0][3]}"
    assert message_call[0][4] == expected_message, f"Expected message {expected_message}, got {message_call[0][4]}"
    
    # Enter送信の確認
    enter_call = send_calls[1]
    assert enter_call[0][3] == expected_target
    assert enter_call[0][4] == "Enter"