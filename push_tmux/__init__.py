#!/usr/bin/env python3
"""
Pushbulletのメッセージをtmuxに送信するCLIツール（パッケージ版）
"""
import click

# メイン CLI グループを定義
@click.group()
def cli():
    """
    Pushbulletのメッセージをtmuxに送信するCLIツール。
    
    主要コマンド:
      device    Pushbulletデバイスの管理 (register/list/delete)
      start     メッセージ待機の開始 (--daemon でデーモンモード)
      send      テスト用のメッセージ送信
    """
    pass


# 各コマンドを動的にインポートして登録
def _register_commands():
    """全てのサブコマンドを登録"""
    # 新しい階層構造のコマンド
    from .commands.device_group import device
    from .commands.start import start
    from .commands.send import send
    
    # サブコマンドを登録
    cli.add_command(device)
    cli.add_command(start) 
    cli.add_command(send)


# コマンドを登録
_register_commands()


# スクリプトエントリーポイント
if __name__ == "__main__":
    cli()