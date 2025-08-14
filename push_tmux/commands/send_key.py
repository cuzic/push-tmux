#!/usr/bin/env python3
"""
Send key command for push-tmux
"""

import asyncio
import click
from ..config import load_config
from ..tmux import send_to_tmux


@click.command("send-key")
@click.argument("message")
@click.option("--session", help="tmuxセッション名")
@click.option("--window", help="tmuxウィンドウ番号")
@click.option("--pane", help="tmuxペイン番号")
def send_key(message, session, window, pane):
    """
    指定されたメッセージを直接tmuxに送信します（テスト用）。
    """

    async def _send_key():
        # 設定ファイルを読み込み
        config = load_config()

        # オプションで設定を上書き
        if session:
            config.setdefault("tmux", {})["target_session"] = session
        if window:
            config.setdefault("tmux", {})["target_window"] = window
        if pane:
            config.setdefault("tmux", {})["target_pane"] = pane

        # tmuxにメッセージを送信
        await send_to_tmux(config, message)

    asyncio.run(_send_key())
