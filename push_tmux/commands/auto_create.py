#!/usr/bin/env python3
"""
Auto device creation command for push-tmux
"""

import asyncio
import click
from asyncpushbullet import AsyncPushbullet
from ..tmux import get_all_sessions
from ..device import _get_device_attr
from ..utils import get_api_key


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="デバイスを作成せず、作成対象のセッションのみ表示します。",
)
def auto_create(dry_run):
    """
    tmuxセッションを調べて、対応するPushbulletデバイスを自動作成します。

    既存のデバイスと照合し、未登録のセッションに対してのみデバイスを作成します。
    """

    async def _auto_create():
        api_key = get_api_key()
        if not api_key:
            return

        # Get all tmux sessions
        click.echo("tmuxセッションを取得中...")
        sessions = await get_all_sessions()

        if not sessions:
            click.echo("tmuxセッションが見つかりませんでした。")
            return

        click.echo(f"検出されたtmuxセッション ({len(sessions)}件):")
        for session in sessions:
            click.echo(f"  - {session}")

        # Get existing Pushbullet devices
        async with AsyncPushbullet(api_key) as pb:
            try:
                devices = pb.get_devices()
                existing_device_names = {
                    _get_device_attr(d, "nickname") for d in devices
                }

                click.echo(f"\n既存のデバイス ({len(existing_device_names)}件):")
                for name in existing_device_names:
                    click.echo(f"  - {name}")

                # Find sessions that don't have corresponding devices
                missing_sessions = [
                    s for s in sessions if s not in existing_device_names
                ]

                if not missing_sessions:
                    click.echo("\n全てのtmuxセッションに対応するデバイスが既に登録されています。")
                    return

                click.echo(f"\n未登録のセッション ({len(missing_sessions)}件):")
                for session in missing_sessions:
                    click.echo(f"  - {session}")

                if dry_run:
                    click.echo("\n[DRY RUN] 以下のデバイスが作成されます:")
                    for session in missing_sessions:
                        click.echo(f"  - {session}")
                    return

                # Create devices for missing sessions
                click.echo("\nデバイスを作成中...")
                created_count = 0
                failed_count = 0

                for session in missing_sessions:
                    try:
                        import json
                        data = {
                            "nickname": session,
                            "type": "stream",
                            "manufacturer": "push-tmux",
                            "model": "CLI",
                            "icon": "system",
                        }
                        device_response = await pb._async_post_data(
                            pb.DEVICES_URL, json=data
                        )
                        click.echo(
                            f"  ✓ デバイス '{session}' を作成しました (ID: {_get_device_attr(device_response, 'iden')})"
                        )
                        created_count += 1
                    except Exception as e:
                        click.echo(f"  ✗ デバイス '{session}' の作成に失敗しました: {e}", err=True)
                        failed_count += 1

                click.echo(
                    f"\n完了: {created_count}件作成, {failed_count}件失敗"
                )

            except Exception as e:
                click.echo(f"エラーが発生しました: {e}", err=True)

    asyncio.run(_auto_create())
