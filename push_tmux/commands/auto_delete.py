#!/usr/bin/env python3
"""
Auto device deletion command for push-tmux
"""

import asyncio
import click
from asyncpushbullet import AsyncPushbullet
from ..tmux import get_all_sessions
from ..device import _get_device_attr
from ..utils import get_api_key

# Device names to exclude from deletion
EXCLUDED_DEVICES = {"main"}


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="デバイスを削除せず、削除対象のデバイスのみ表示します。",
)
@click.option(
    "--all",
    "delete_all",
    is_flag=True,
    help="push-tmux以外のデバイスも対象に含めます（デフォルトはpush-tmuxのみ）。",
)
def auto_delete(dry_run, delete_all):
    """
    tmuxセッションが存在しないPushbulletデバイスを自動削除します。

    デフォルトでは、push-tmuxが作成したデバイス（manufacturer="push-tmux"）のみが対象です。
    """

    async def _auto_delete():
        api_key = get_api_key()
        if not api_key:
            return

        # Get all tmux sessions
        click.echo("tmuxセッションを取得中...")
        sessions = await get_all_sessions()
        session_set = set(sessions)

        if sessions:
            click.echo(f"検出されたtmuxセッション ({len(sessions)}件):")
            for session in sessions:
                click.echo(f"  - {session}")
        else:
            click.echo("tmuxセッションが見つかりませんでした。")

        # Get existing Pushbullet devices
        async with AsyncPushbullet(api_key) as pb:
            try:
                devices = pb.get_devices()

                # Filter devices based on manufacturer
                if delete_all:
                    target_devices = devices
                    click.echo(f"\n全てのデバイス ({len(devices)}件)を対象にします。")
                else:
                    target_devices = [
                        d
                        for d in devices
                        if _get_device_attr(d, "manufacturer") == "push-tmux"
                    ]
                    click.echo(
                        f"\npush-tmuxが作成したデバイス ({len(target_devices)}件):"
                    )
                    for device in target_devices:
                        click.echo(f"  - {_get_device_attr(device, 'nickname')}")

                if not target_devices:
                    click.echo("\n対象デバイスがありません。")
                    return

                # Check for excluded devices
                excluded_found = [
                    d for d in target_devices
                    if _get_device_attr(d, "nickname") in EXCLUDED_DEVICES
                ]
                if excluded_found:
                    click.echo(f"\n除外されたデバイス ({len(excluded_found)}件):")
                    for device in excluded_found:
                        click.echo(f"  - {_get_device_attr(device, 'nickname')} (削除をスキップ)")

                # Find orphaned devices (devices without corresponding tmux sessions)
                # Exclude certain device names (e.g., "main")
                orphaned_devices = [
                    d
                    for d in target_devices
                    if _get_device_attr(d, "nickname") not in session_set
                    and _get_device_attr(d, "nickname") not in EXCLUDED_DEVICES
                ]

                if not orphaned_devices:
                    click.echo(
                        "\n全てのデバイスに対応するtmuxセッションが存在します。削除対象はありません。"
                    )
                    return

                click.echo(f"\n孤立したデバイス ({len(orphaned_devices)}件):")
                for device in orphaned_devices:
                    device_name = _get_device_attr(device, "nickname")
                    device_id = _get_device_attr(device, "iden")
                    click.echo(f"  - {device_name} (ID: {device_id})")

                if dry_run:
                    click.echo("\n[DRY RUN] 以下のデバイスが削除されます:")
                    for device in orphaned_devices:
                        click.echo(f"  - {_get_device_attr(device, 'nickname')}")
                    return

                # Delete orphaned devices
                click.echo("\nデバイスを削除中...")
                deleted_count = 0
                failed_count = 0

                for device in orphaned_devices:
                    device_name = _get_device_attr(device, "nickname")
                    device_id = _get_device_attr(device, "iden")
                    try:
                        await pb._async_delete_data(f"{pb.DEVICES_URL}/{device_id}")
                        click.echo(f"  ✓ デバイス '{device_name}' を削除しました")
                        deleted_count += 1
                    except Exception as e:
                        click.echo(
                            f"  ✗ デバイス '{device_name}' の削除に失敗しました: {e}",
                            err=True,
                        )
                        failed_count += 1

                click.echo(f"\n完了: {deleted_count}件削除, {failed_count}件失敗")

            except Exception as e:
                click.echo(f"エラーが発生しました: {e}", err=True)

    asyncio.run(_auto_delete())
