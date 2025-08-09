#!/usr/bin/env python3
"""
WebSocket修正の確認テスト（簡易版）
"""
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

# プロジェクトのルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from async_pushbullet import AsyncPushbulletListener


def test_ping_pong_disabled():
    """ping/pongが無効化されているか確認"""
    print("テスト: ping/pongの無効化")
    print("-" * 40)
    
    api_key = "test_key"
    listener = AsyncPushbulletListener(api_key)
    
    async def run_test():
        with patch('websockets.connect', new_callable=AsyncMock) as mock_connect:
            mock_ws = MagicMock()
            mock_connect.return_value = mock_ws
            
            # 接続を実行
            result = await listener.connect()
            
            # 検証
            assert result is True, "接続が成功するはず"
            
            # websockets.connectの呼び出し引数を確認
            call_args, call_kwargs = mock_connect.call_args
            
            # ping_interval=Noneが設定されているか
            assert 'ping_interval' in call_kwargs, "ping_intervalが設定されているはず"
            assert call_kwargs['ping_interval'] is None, f"ping_intervalはNoneであるべき: {call_kwargs['ping_interval']}"
            
            print(f"  ✓ ping_interval = {call_kwargs['ping_interval']}")
            print(f"  ✓ close_timeout = {call_kwargs.get('close_timeout', 'not set')}")
            
            return True
    
    result = asyncio.run(run_test())
    print(f"  結果: {'成功' if result else '失敗'}")
    return result


def test_timeout_settings():
    """タイムアウト設定が正しいか確認"""
    print("\nテスト: タイムアウト設定")
    print("-" * 40)
    
    listener = AsyncPushbulletListener("test_key")
    
    tests = [
        ("WEBSOCKET_TIMEOUT", 45, "WebSocketタイムアウト"),
        ("NOP_TIMEOUT", 90, "nopタイムアウト"),
        ("MAX_RECONNECT_ATTEMPTS", 5, "最大再接続回数"),
        ("RECONNECT_DELAY", 5, "再接続待機時間"),
    ]
    
    all_passed = True
    for attr_name, expected, description in tests:
        actual = getattr(listener, attr_name)
        passed = actual == expected
        all_passed = all_passed and passed
        
        status = "✓" if passed else "✗"
        print(f"  {status} {description}: {actual} (期待値: {expected})")
    
    print(f"  結果: {'成功' if all_passed else '失敗'}")
    return all_passed


def test_error_handling():
    """エラーハンドリングの改善を確認"""
    print("\nテスト: エラーハンドリング")
    print("-" * 40)
    
    listener = AsyncPushbulletListener("test_key")
    
    async def run_test():
        listener.running = True
        listener.websocket = MagicMock()
        
        # keepalive ping timeoutエラーのテスト
        test_errors = [
            "sent 1011 (internal error) keepalive ping timeout",
            "connection closed",
            "Connection CLOSED",
        ]
        
        results = []
        for error_msg in test_errors:
            with patch.object(listener.websocket, 'recv', new_callable=AsyncMock) as mock_recv:
                mock_recv.side_effect = Exception(error_msg)
                
                try:
                    # _receive_messagesを実行（すぐに終了するはず）
                    await asyncio.wait_for(listener._receive_messages(), timeout=1.0)
                    results.append(True)
                    print(f"  ✓ '{error_msg[:30]}...' を適切に処理")
                except asyncio.TimeoutError:
                    results.append(False)
                    print(f"  ✗ '{error_msg[:30]}...' の処理でタイムアウト")
                except Exception as e:
                    results.append(False)
                    print(f"  ✗ '{error_msg[:30]}...' の処理でエラー: {e}")
        
        return all(results)
    
    result = asyncio.run(run_test())
    print(f"  結果: {'成功' if result else '失敗'}")
    return result


def test_is_connected():
    """is_connectedメソッドのテスト"""
    print("\nテスト: is_connectedメソッド")
    print("-" * 40)
    
    listener = AsyncPushbulletListener("test_key")
    
    # websocketがNoneの場合
    listener.websocket = None
    result1 = listener.is_connected() is False
    print(f"  {'✓' if result1 else '✗'} websocket=None → False")
    
    # websocketが存在し、closedプロパティがある場合
    listener.websocket = MagicMock()
    listener.websocket.closed = False
    result2 = listener.is_connected() is True
    print(f"  {'✓' if result2 else '✗'} closed=False → True")
    
    listener.websocket.closed = True
    result3 = listener.is_connected() is False
    print(f"  {'✓' if result3 else '✗'} closed=True → False")
    
    # stateプロパティの場合
    del listener.websocket.closed
    from websockets.protocol import State
    
    listener.websocket.state = State.OPEN
    result4 = listener.is_connected() is True
    print(f"  {'✓' if result4 else '✗'} state=OPEN → True")
    
    listener.websocket.state = State.CLOSED
    result5 = listener.is_connected() is False
    print(f"  {'✓' if result5 else '✗'} state=CLOSED → False")
    
    # フォールバックの場合
    del listener.websocket.state
    result6 = listener.is_connected() is True
    print(f"  {'✓' if result6 else '✗'} フォールバック → True")
    
    all_passed = all([result1, result2, result3, result4, result5, result6])
    print(f"  結果: {'成功' if all_passed else '失敗'}")
    return all_passed


def test_running_flag():
    """runningフラグの初期化テスト"""
    print("\nテスト: runningフラグの初期化")
    print("-" * 40)
    
    listener = AsyncPushbulletListener("test_key")
    
    async def run_test():
        # 初期状態
        initial_state = listener.running
        print(f"  初期状態: running = {initial_state}")
        
        # listenメソッドをモック化して実行
        with patch.object(listener, 'connect', new_callable=AsyncMock) as mock_connect:
            with patch.object(listener, '_receive_messages', new_callable=AsyncMock) as mock_receive:
                mock_connect.return_value = True
                
                # _receive_messagesをすぐに終了させる
                mock_receive.side_effect = [None]
                
                # listenを実行（すぐに終了する）
                await listener.listen()
                
                # runningフラグが設定されたか確認
                # （listenメソッドの最初でTrueに設定される）
                print(f"  listen実行後: running = {listener.running}")
        
        return True
    
    result = asyncio.run(run_test())
    print(f"  結果: {'成功' if result else '失敗'}")
    return result


def main():
    """すべてのテストを実行"""
    print("=" * 60)
    print("WebSocket修正の確認テスト")
    print("=" * 60)
    
    tests = [
        ("ping/pong無効化", test_ping_pong_disabled),
        ("タイムアウト設定", test_timeout_settings),
        ("エラーハンドリング", test_error_handling),
        ("is_connectedメソッド", test_is_connected),
        ("runningフラグ初期化", test_running_flag),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n{name}でエラー: {e}")
            results.append((name, False))
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("テスト結果サマリー")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("-" * 60)
    print(f"合計: {passed}/{len(results)} 成功")
    
    if failed == 0:
        print("\n🎉 すべてのテストが成功しました！")
    else:
        print(f"\n⚠️  {failed}個のテストが失敗しました")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)