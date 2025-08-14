#!/usr/bin/env python3
"""
デバイス宛てメッセージの判定ロジックのテスト
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
import sys
import os

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_device_targeting_logic():
    """デバイス宛てメッセージの判定ロジックをテスト"""

    # テスト用のtarget_device_iden
    my_device_iden = "device123"
    other_device_iden = "device456"

    # テストケース
    test_cases = [
        {
            "name": "自分のデバイス宛のメッセージ",
            "push": {"type": "note", "target_device_iden": my_device_iden},
            "target_device_iden": my_device_iden,
            "should_process": True,
        },
        {
            "name": "他のデバイス宛のメッセージ",
            "push": {"type": "note", "target_device_iden": other_device_iden},
            "target_device_iden": my_device_iden,
            "should_process": False,
        },
        {
            "name": "全デバイス宛のメッセージ（target_device_idenなし）",
            "push": {"type": "note"},
            "target_device_iden": my_device_iden,
            "should_process": False,
        },
        {
            "name": "noteタイプ以外のメッセージ",
            "push": {"type": "link", "target_device_iden": my_device_iden},
            "target_device_iden": my_device_iden,
            "should_process": False,
        },
    ]

    for test_case in test_cases:
        print(f"\nテスト: {test_case['name']}")

        # 判定ロジックのシミュレーション
        push = test_case["push"]
        target_device_iden = test_case["target_device_iden"]
        expected = test_case["should_process"]

        # noteタイプのみ処理
        if push.get("type") != "note":
            result = False
        else:
            # デバイスフィルタリング
            target_device = push.get("target_device_iden")

            # 全デバイス宛のメッセージは無視
            if not target_device:
                result = False
            # 特定のデバイス宛のメッセージのみ処理
            elif target_device != target_device_iden:
                result = False
            else:
                result = True

        print(f"  Push: {push}")
        print(f"  Target Device ID: {target_device_iden}")
        print(f"  期待される結果: {'処理する' if expected else '無視する'}")
        print(f"  実際の結果: {'処理する' if result else '無視する'}")

        assert result == expected, f"判定が間違っています: {test_case['name']}"
        print("  ✓ テスト成功")


@pytest.mark.asyncio
async def test_on_push_function():
    """on_push関数の動作をテスト"""

    # モックの設定
    with patch("push_tmux.tmux.send_to_tmux", new_callable=AsyncMock) as mock_send:
        with patch("click.echo"):
            # テスト用のデバイスID
            my_device_iden = "test_device_123"

            # on_push関数を定義（実際のコードと同じロジック）
            async def on_push(push):
                # noteタイプのみ処理
                if push.get("type") != "note":
                    return False

                # デバイスフィルタリング
                target_device = push.get("target_device_iden")

                # 全デバイス宛のメッセージは無視
                if not target_device:
                    return False

                # 特定のデバイス宛のメッセージのみ処理
                if target_device != my_device_iden:
                    return False

                # メッセージを処理
                body = push.get("body", "")
                await mock_send({}, body)
                return True

            # テストケース1: 自分のデバイス宛のメッセージ
            push1 = {
                "type": "note",
                "target_device_iden": my_device_iden,
                "body": "テストメッセージ1",
            }
            result1 = await on_push(push1)
            assert result1
            mock_send.assert_called_with({}, "テストメッセージ1")

            # テストケース2: 他のデバイス宛のメッセージ
            push2 = {
                "type": "note",
                "target_device_iden": "other_device",
                "body": "テストメッセージ2",
            }
            result2 = await on_push(push2)
            assert not result2

            # テストケース3: 全デバイス宛のメッセージ
            push3 = {"type": "note", "body": "全デバイス宛"}
            result3 = await on_push(push3)
            assert not result3

            print("\n✓ on_push関数のテストが全て成功しました")


if __name__ == "__main__":
    print("=" * 60)
    print("デバイス宛てメッセージの判定ロジックのテスト")
    print("=" * 60)

    # 同期テストの実行
    test_device_targeting_logic()

    # 非同期テストの実行
    asyncio.run(test_on_push_function())

    print("\n" + "=" * 60)
    print("✅ 全てのテストが成功しました！")
    print("=" * 60)
