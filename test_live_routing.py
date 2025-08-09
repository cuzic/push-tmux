#!/usr/bin/env python3
"""
実際のPushbullet経由でのルーティングテスト
"""
import asyncio
import os
from async_pushbullet import AsyncPushbullet
from dotenv import load_dotenv

load_dotenv()

async def send_test_message():
    """テストメッセージを送信"""
    api_key = os.getenv('PUSHBULLET_TOKEN')
    if not api_key:
        print("エラー: PUSHBULLET_TOKEN環境変数が設定されていません")
        return
    
    async with AsyncPushbullet(api_key) as pb:
        # デバイス一覧を取得
        devices = await pb.get_devices()
        
        # push-tmuxデバイスを探す
        push_tmux_device = None
        for device in devices:
            if device.get('nickname') == 'push-tmux':
                push_tmux_device = device
                break
        
        if not push_tmux_device:
            print("エラー: push-tmuxデバイスが見つかりません")
            return
        
        print("=" * 60)
        print("Pushbullet経由のルーティングテスト")
        print("=" * 60)
        print(f"デバイス: {push_tmux_device['nickname']} (ID: {push_tmux_device['iden']})")
        print("-" * 60)
        
        # テストメッセージを送信
        message = "echo '[ROUTING TEST] This should appear in push-tmux session'"
        print(f"送信メッセージ: {message}")
        
        result = await pb.push_note(
            title="Routing Test",
            body=message,
            device_iden=push_tmux_device['iden']
        )
        
        print(f"✅ メッセージ送信完了 (ID: {result['iden']})")
        print("\n説明:")
        print("1. push-tmux listenが実行中の場合")
        print("2. メッセージはpush-tmuxセッションに送信されるはず")
        print("3. push-tmuxセッションで上記のechoコマンドが実行される")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(send_test_message())