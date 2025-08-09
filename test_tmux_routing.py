#!/usr/bin/env python3
"""
tmuxセッションルーティングの動作確認スクリプト
"""
import asyncio
import os
from push_tmux import send_to_tmux

async def test_routing():
    """実際のルーティングをテスト"""
    
    # 現在のtmuxセッション一覧を確認
    result = await asyncio.create_subprocess_exec(
        'tmux', 'ls', '-F', '#{session_name}',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await result.communicate()
    sessions = stdout.decode().strip().split('\n')
    
    print("=" * 60)
    print("tmuxセッションルーティングテスト")
    print("=" * 60)
    print(f"現在のtmuxセッション: {sessions}")
    print("-" * 60)
    
    # テストケース1: デバイス名 = push-tmux
    if 'push-tmux' in sessions:
        print("\nテスト1: device_name='push-tmux' でメッセージ送信")
        print("期待結果: push-tmuxセッションに送信される")
        config = {}
        await send_to_tmux(config, "echo 'Test message to push-tmux'", device_name='push-tmux')
        print("✅ 完了")
    else:
        print("\n⚠️  push-tmuxセッションが存在しません")
    
    # テストケース2: デバイス名 = 存在しないセッション
    print("\nテスト2: device_name='non-existent' でメッセージ送信")
    print("期待結果: 現在のセッションにフォールバック")
    config = {}
    await send_to_tmux(config, "echo 'Test fallback message'", device_name='non-existent')
    print("✅ 完了")
    
    # テストケース3: config設定を優先
    print("\nテスト3: config設定でセッションを明示指定")
    print("期待結果: config設定のセッションに送信")
    if len(sessions) > 1:
        target = sessions[1] if sessions[0] == 'push-tmux' else sessions[0]
        config = {'tmux': {'target_session': target}}
        print(f"config設定: target_session='{target}'")
        await send_to_tmux(config, f"echo 'Config override to {target}'", device_name='push-tmux')
        print("✅ 完了")
    else:
        print("⚠️  複数セッションが必要です")
    
    print("\n" + "=" * 60)
    print("テスト完了")
    print("各tmuxセッションでメッセージが表示されているか確認してください")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_routing())