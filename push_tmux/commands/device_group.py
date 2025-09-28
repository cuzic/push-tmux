#!/usr/bin/env python3
"""
Device management command group for push-tmux
"""

import click


# デバイス管理のサブコマンドグループ
@click.group("device")
def device():
    """
    Pushbulletデバイスの管理を行います。

    デバイスの登録、一覧表示、削除などの操作が可能です。
    """
    pass


def _register_device_commands():
    """デバイス関連のサブコマンドを登録"""
    # 既存のコマンドをインポートして登録
    from .register import register
    from .list_devices import list_devices
    from .delete_devices import delete_devices

    # registerコマンドはすでに@click.commandデコレータ付きなのでそのまま追加
    device.add_command(register)

    # list_devicesとdelete_devicesには@click.commandがないので、Click Commandとして作成
    list_cmd = click.Command(
        "list",
        callback=list_devices,
        help="登録されているPushbulletデバイスの一覧を表示します。",
    )

    # delete_devices is already decorated with options, just needs @click.command
    delete_cmd = click.command("delete", help="Pushbulletデバイスを削除します。")(delete_devices)

    device.add_command(list_cmd)
    device.add_command(delete_cmd)


# コマンドを登録
_register_device_commands()
