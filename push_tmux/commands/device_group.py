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

    # コマンド名を調整してデバイスグループに追加
    register_cmd = click.Command(
        "register",
        callback=register.callback,
        params=register.params,
        help="新しいPushbulletデバイスとして登録します。",
    )

    list_cmd = click.Command(
        "list",
        callback=list_devices.callback,
        params=list_devices.params,
        help="登録されているPushbulletデバイスの一覧を表示します。",
    )

    delete_cmd = click.Command(
        "delete",
        callback=delete_devices.callback,
        params=delete_devices.params,
        help="Pushbulletデバイスを削除します。",
    )

    device.add_command(register_cmd)
    device.add_command(list_cmd)
    device.add_command(delete_cmd)


# コマンドを登録
_register_device_commands()
