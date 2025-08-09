#!/usr/bin/env python3
"""
リスナーの安定性をテストするスクリプト
"""
import asyncio
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from async_pushbullet import AsyncPushbulletListener

load_dotenv()

async def test_stability():
    """安定性テスト"""
    api_key = os.getenv('PUSHBULLET_TOKEN')
    
    if not api_key:
        print("エラー: PUSHBULLET_TOKEN環境変数が設定されていません")
        return
    
    print("=" * 60)
    print("リスナー安定性テスト")
    print("=" * 60)
    print(f"開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)
    
    # 統計情報
    stats = {
        'start_time': time.time(),
        'nop_count': 0,
        'tickle_count': 0,
        'push_count': 0,
        'errors': 0,
        'reconnects': 0,
        'last_message_time': time.time()
    }
    
    async def on_push(push):
        """プッシュハンドラー"""
        now = time.time()
        stats['last_message_time'] = now
        
        msg_type = push.get('type', 'unknown')
        if msg_type == 'nop':
            stats['nop_count'] += 1
            print(f"[{datetime.now().strftime('%H:%M:%S')}] nop受信 (合計: {stats['nop_count']})")
        elif msg_type == 'tickle':
            stats['tickle_count'] += 1
            print(f"[{datetime.now().strftime('%H:%M:%S')}] tickle受信")
        else:
            stats['push_count'] += 1
            print(f"[{datetime.now().strftime('%H:%M:%S')}] push受信: {msg_type}")
            if msg_type == 'note':
                print(f"  タイトル: {push.get('title', 'N/A')}")
                print(f"  本文: {push.get('body', 'N/A')[:50]}")
    
    # カスタムリスナー
    class MonitoringListener(AsyncPushbulletListener):
        async def connect(self):
            result = await super().connect()
            if result:
                stats['reconnects'] += 1
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 接続成功 (接続回数: {stats['reconnects']})")
            return result
        
        async def _receive_messages(self):
            try:
                await super()._receive_messages()
            except Exception as e:
                stats['errors'] += 1
                print(f"[{datetime.now().strftime('%H:%M:%S')}] エラー: {e}")
                raise
    
    # リスナーを起動
    listener = MonitoringListener(api_key, on_push, debug=False)  # デバッグモードOFF
    
    # 60秒間実行
    try:
        print("リスナーを開始します（60秒間実行）...")
        print("Ctrl+Cで中断できます")
        print("-" * 60)
        
        await asyncio.wait_for(listener.run(), timeout=60)
    except asyncio.TimeoutError:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] テスト終了（60秒経過）")
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ユーザーにより中断")
    finally:
        if listener.running:
            await listener.disconnect()
    
    # 結果表示
    runtime = time.time() - stats['start_time']
    print("\n" + "=" * 60)
    print("テスト結果:")
    print(f"  実行時間: {runtime:.1f}秒")
    print(f"  nopメッセージ: {stats['nop_count']}回")
    print(f"  tickleメッセージ: {stats['tickle_count']}回")
    print(f"  pushメッセージ: {stats['push_count']}回")
    print(f"  エラー: {stats['errors']}回")
    print(f"  再接続: {stats['reconnects']}回")
    
    if stats['nop_count'] > 0:
        avg_nop_interval = runtime / stats['nop_count']
        print(f"  平均nop間隔: {avg_nop_interval:.1f}秒")
    
    last_msg_ago = time.time() - stats['last_message_time']
    print(f"  最後のメッセージ: {last_msg_ago:.1f}秒前")
    
    # 判定
    print("\n判定:")
    if stats['errors'] == 0 and stats['reconnects'] <= 2:
        print("  ✅ 安定動作")
    elif stats['errors'] <= 2 and stats['reconnects'] <= 3:
        print("  ⚠️  軽微な問題あり")
    else:
        print("  ❌ 不安定")
    
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_stability())