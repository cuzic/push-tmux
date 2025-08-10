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


@click.command()
@click.option('--name', help='デバイス名（未指定時は環境変数DEVICE_NAME）')
def register(name):
    """
    新しいPushbulletデバイスとして登録します。
    """
    async def _register():
        api_key = os.getenv('PUSHBULLET_TOKEN')
        if not api_key:
            click.echo("エラー: PUSHBULLET_TOKEN環境変数が設定されていません。", err=True)
            return
        
        device_name = name if name else get_device_name()
        
        async with AsyncPushbullet(api_key) as pb:
            try:
                devices = pb.get_devices()  # get_devicesは同期メソッド
                existing_device = next((d for d in devices if _get_device_attr(d, 'nickname') == device_name), None)
                
                if existing_device:
                    click.echo(f"デバイス '{device_name}' は既に登録されています。")
                    click.echo(f"デバイスID: {_get_device_attr(existing_device, 'iden')}")
                    return
                
                device = await pb.async_new_device(device_name)
                click.echo(f"デバイス '{device_name}' を登録しました。")
                click.echo(f"デバイスID: {_get_device_attr(device, 'iden')}")
                
            except Exception as e:
                click.echo(f"デバイス登録中にエラーが発生しました: {e}", err=True)
    
    asyncio.run(_register())