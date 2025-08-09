#!/usr/bin/env python3
"""
リスナーの基本動作をテストするスクリプト
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from async_pushbullet import AsyncPushbulletListener

load_dotenv()

async def test_basic_listener():
    """基本的なリスナーのテスト"""
    api_key = os.getenv('PUSHBULLET_TOKEN')
    
    if not api_key:
        print("エラー: PUSHBULLET_TOKEN環境変数が設定されていません")
        return
    
    print("テスト開始: リスナーの基本動作確認")
    print("=" * 60)
    
    async def on_push(push):
        """プッシュハンドラー"""
        print(f"受信: {push.get('type', 'unknown')}")
        if push.get('type') == 'note':
            print(f"  タイトル: {push.get('title', 'N/A')}")
            print(f"  本文: {push.get('body', 'N/A')}")
    
    # デバッグモードでリスナーを作成
    listener = AsyncPushbulletListener(api_key, on_push, debug=True)
    
    print(f"初期状態:")
    print(f"  running: {listener.running}")
    print(f"  websocket: {listener.websocket}")
    print("")
    
    # 10秒間だけ実行
    try:
        print("リスナーを開始します（10秒間実行）...")
        await asyncio.wait_for(listener.run(), timeout=10)
    except asyncio.TimeoutError:
        print("\nタイムアウト（正常）")
    except Exception as e:
        print(f"\nエラー: {e}")
    finally:
        print(f"\n終了時の状態:")
        print(f"  running: {listener.running}")
        print(f"  websocket: {listener.websocket}")
        
        if listener.running:
            print("\n手動で切断します...")
            await listener.disconnect()
    
    print("\nテスト完了")

if __name__ == "__main__":
    asyncio.run(test_basic_listener())