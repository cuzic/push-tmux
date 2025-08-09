#!/usr/bin/env python3
"""
自動ルーティング機能の動作確認スクリプト
"""
import asyncio
import os
from async_pushbullet import AsyncPushbullet
from dotenv import load_dotenv

load_dotenv()

async def test_auto_route():
    """自動ルーティングのテスト"""
    api_key = os.getenv('PUSHBULLET_TOKEN')
    if not api_key:
        print("エラー: PUSHBULLET_TOKEN環境変数が設定されていません")
        return
    
    # 現在のtmuxセッション一覧を確認
    result = await asyncio.create_subprocess_exec(
        'tmux', 'ls', '-F', '#{session_name}',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await result.communicate()
    sessions = stdout.decode().strip().split('\n') if stdout else []
    
    print("=" * 60)
    print("自動ルーティング機能テスト")
    print("=" * 60)
    print(f"現在のtmuxセッション: {sessions}")
    print("-" * 60)
    
    async with AsyncPushbullet(api_key) as pb:
        # デバイス一覧を取得
        devices = await pb.get_devices(active_only=True)
        
        print("\nアクティブなデバイス:")
        for device in devices:
            nickname = device.get('nickname', 'N/A')
            iden = device['iden']
            
            # セッション存在確認
            session_status = "✓ セッションあり" if nickname in sessions else "✗ セッションなし"
            print(f"  - {nickname} ({iden[:8]}...) [{session_status}]")
        
        print("\n" + "-" * 60)
        print("テストメッセージを送信:")
        
        # 各デバイスにテストメッセージを送信
        for device in devices:
            nickname = device.get('nickname', 'N/A')
            iden = device['iden']
            
            if nickname in sessions:
                message = f"echo '[AUTO-ROUTE TEST] Message for {nickname}'"
                print(f"\n  → {nickname}: {message}")
                
                result = await pb.push_note(
                    title="Auto-Route Test",
                    body=message,
                    device_iden=iden
                )
                print(f"    送信完了 (ID: {result['iden'][:8]}...)")
            else:
                print(f"\n  → {nickname}: スキップ（セッションなし）")
    
    print("\n" + "=" * 60)
    print("説明:")
    print("1. --auto-routeモードで実行すると")
    print("2. 全デバイスのメッセージを受信")
    print("3. デバイス名と同じtmuxセッションがあれば自動送信")
    print("4. セッションがなければスキップ")
    print("\n実行コマンド:")
    print("  python push_tmux.py listen --auto-route")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_auto_route())