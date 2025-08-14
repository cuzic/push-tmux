#!/usr/bin/env python3
"""
Device listing command for push-tmux
"""

import asyncio
import click
import os
from asyncpushbullet import AsyncPushbullet
from ..device import _get_device_attr


@click.command("list-devices")
def list_devices():
    """
    登録されているPushbulletデバイスの一覧を表示します。
    """

    async def _list_devices():
        api_key = os.getenv("PUSHBULLET_TOKEN")
        if not api_key:
            click.echo(
                "エラー: PUSHBULLET_TOKEN環境変数が設定されていません。", err=True
            )
            return

        async with AsyncPushbullet(api_key) as pb:
            try:
                devices = pb.get_devices()  # get_devicesは同期メソッド

                if not devices:
                    click.echo("登録されているデバイスがありません。")
                    return

                click.echo(f"登録されているデバイス ({len(devices)}件):")
                click.echo("-" * 50)

                for device in devices:
                    status = (
                        "アクティブ"
                        if _get_device_attr(device, "active") is not False
                        else "非アクティブ"
                    )
                    click.echo(f"名前: {_get_device_attr(device, 'nickname') or 'N/A'}")
                    click.echo(f"ID: {_get_device_attr(device, 'iden')}")
                    click.echo(f"ステータス: {status}")
                    click.echo(
                        f"作成日時: {_get_device_attr(device, 'created') or 'N/A'}"
                    )
                    click.echo("-" * 30)

            except Exception as e:
                click.echo(f"デバイス一覧取得中にエラーが発生しました: {e}", err=True)

    asyncio.run(_list_devices())
