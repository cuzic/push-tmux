#!/usr/bin/env python3
"""
Common utility functions for push-tmux
"""

import os
import click


def get_api_key():
    """
    PUSHBULLET_TOKEN環境変数からAPIキーを取得

    Returns:
        str: APIキー、設定されていない場合はNone
    """
    api_key = os.getenv("PUSHBULLET_TOKEN")
    if not api_key:
        click.echo("エラー: PUSHBULLET_TOKEN環境変数が設定されていません。", err=True)
    return api_key


def require_api_key():
    """
    APIキーが必須の処理で使用するデコレータ用関数
    APIキーがない場合はエラーメッセージを表示してNoneを返す
    """
    api_key = get_api_key()
    if not api_key:
        return None
    return api_key