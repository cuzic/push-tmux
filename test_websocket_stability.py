#!/usr/bin/env python3
"""
WebSocket接続の安定性をテストするスクリプト
"""
import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# プロジェクトのルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from async_pushbullet import AsyncPushbulletListener

load_dotenv()

async def test_websocket_stability():
    """WebSocket接続の安定性をテスト"""
    api_key = os.getenv('PUSHBULLET_TOKEN')
    if not api_key:
        print("エラー: PUSHBULLET_TOKEN環境変数が設定されていません")
        return
    
    # 統計情報
    stats = {
        'start_time': datetime.now(),
        'messages_received': 0,
        'nop_count': 0,
        'tickle_count': 0,
        'push_count': 0,
        'errors': 0,
        'reconnects': 0
    }
    
    async def on_push_handler(push):
        """プッシュハンドラー"""
        stats['messages_received'] += 1
        
        msg_type = push.get('type', 'unknown')
        if msg_type == 'nop':
            stats['nop_count'] += 1
        elif msg_type == 'tickle':
            stats['tickle_count'] += 1
        else:
            stats['push_count'] += 1
        
        # 統計を表示
        runtime = (datetime.now() - stats['start_time']).total_seconds()
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 統計情報:")
        print(f"  実行時間: {runtime:.0f}秒")
        print(f"  受信メッセージ数: {stats['messages_received']}")
        print(f"  - nop: {stats['nop_count']}")
        print(f"  - tickle: {stats['tickle_count']}")
        print(f"  - push: {stats['push_count']}")
        print(f"  エラー数: {stats['errors']}")
        print(f"  再接続回数: {stats['reconnects']}")
        
        if msg_type not in ['nop']:
            print(f"\n  受信内容: {msg_type}")
            if msg_type == 'note':
                print(f"    タイトル: {push.get('title', 'N/A')}")
                print(f"    本文: {push.get('body', 'N/A')[:50]}...")
    
    # リスナーをカスタマイズ
    class StabilityTestListener(AsyncPushbulletListener):
        async def connect(self):
            result = await super().connect()
            if result:
                stats['reconnects'] += 1
            return result
        
        async def _receive_messages(self):
            try:
                await super()._receive_messages()
            except Exception as e:
                stats['errors'] += 1
                raise
    
    print("=" * 60)
    print("WebSocket接続安定性テスト")
    print("=" * 60)
    print(f"開始時刻: {stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
    print("Ctrl+Cで終了します")
    print("-" * 60)
    
    # デバッグモードでリスナーを起動
    listener = StabilityTestListener(api_key, on_push_handler, debug=True)
    
    try:
        await listener.run()
    except KeyboardInterrupt:
        print("\n\nテストを終了します...")
    
    # 最終統計
    runtime = (datetime.now() - stats['start_time']).total_seconds()
    print("\n" + "=" * 60)
    print("最終統計:")
    print(f"  総実行時間: {runtime:.0f}秒 ({runtime/60:.1f}分)")
    print(f"  総受信メッセージ数: {stats['messages_received']}")
    print(f"  平均受信間隔: {runtime/max(stats['messages_received'], 1):.1f}秒")
    print(f"  エラー率: {stats['errors']/max(stats['messages_received'], 1)*100:.1f}%")
    print(f"  再接続回数: {stats['reconnects']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_websocket_stability())