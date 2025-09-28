#!/usr/bin/env python3
"""
Device registration command for push-tmux
"""

import asyncio
import click
import os
from asyncpushbullet import AsyncPushbullet
from ..config import get_device_name
from ..device import _get_device_attr
from ..utils import get_api_key


@click.command()
@click.option("--name", help="デバイス名（未指定時は環境変数DEVICE_NAME）")
def register(name):
    """
    新しいPushbulletデバイスとして登録します。
    """

    async def _register():
        api_key = get_api_key()
        if not api_key:
            return

        device_name = name if name else get_device_name()

        async with AsyncPushbullet(api_key) as pb:
            try:
                devices = pb.get_devices()  # get_devicesは同期メソッド
                existing_device = next(
                    (
                        d
                        for d in devices
                        if _get_device_attr(d, "nickname") == device_name
                    ),
                    None,
                )

                if existing_device:
                    click.echo(f"デバイス '{device_name}' は既に登録されています。")
                    click.echo(
                        f"デバイスID: {_get_device_attr(existing_device, 'iden')}"
                    )
                    return

                # Work around asyncpushbullet bug: use API directly
                import json
                data = {
                    "nickname": device_name,
                    "type": "stream",
                    "manufacturer": "push-tmux",
                    "model": "CLI",
                    "icon": "system"
                }
                device_response = await pb._async_post_data(
                    pb.DEVICES_URL,
                    json=data  # Use json parameter instead of data
                )
                device = device_response
                click.echo(f"デバイス '{device_name}' を登録しました。")
                click.echo(f"デバイスID: {_get_device_attr(device, 'iden')}")

            except Exception as e:
                click.echo(f"デバイス登録中にエラーが発生しました: {e}", err=True)
                # デバッグ情報を表示
                if "--debug" in os.sys.argv:
                    import traceback
                    traceback.print_exc()

    asyncio.run(_register())
