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
    """
    pass


# 各コマンドを動的にインポートして登録
def _register_commands():
    """全てのサブコマンドを登録"""
    from .commands.register import register
    from .commands.list_devices import list_devices  
    from .commands.delete_devices import delete_devices
    from .commands.send_key import send_key
    from .commands.listen import listen
    from .commands.daemon import daemon
    
    # サブコマンドを登録
    cli.add_command(register)
    cli.add_command(list_devices)
    cli.add_command(delete_devices)
    cli.add_command(send_key)
    cli.add_command(listen)
    cli.add_command(daemon)


# コマンドを登録
_register_commands()


# スクリプトエントリーポイント
if __name__ == "__main__":
    cli()