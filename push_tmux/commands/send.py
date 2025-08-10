#!/usr/bin/env python3
"""
Send command for push-tmux (formerly send-key)
"""
import asyncio
import click
from ..config import load_config
from ..tmux import send_to_tmux


@click.command('send')
@click.argument('message')
@click.option('--session', help='tmuxセッション名')
@click.option('--window', help='tmuxウィンドウ番号') 
@click.option('--pane', help='tmuxペイン番号')
def send(message, session, window, pane):
    """
    指定されたメッセージを直接tmuxに送信します（テスト用）。
    
    MESSAGE: 送信するメッセージまたはコマンド
    """
    async def _send_message():
        # 設定ファイルを読み込み
        config = load_config()
        
        # オプションで設定を上書き
        if session:
            config.setdefault('tmux', {})['target_session'] = session
        if window:
            config.setdefault('tmux', {})['target_window'] = window
        if pane:
            config.setdefault('tmux', {})['target_pane'] = pane
        
        # tmuxにメッセージを送信
        await send_to_tmux(config, message)
    
    asyncio.run(_send_message())