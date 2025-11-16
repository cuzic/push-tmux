#!/usr/bin/env python3
"""
Auto device sync command for push-tmux
"""

import asyncio
import click
from asyncpushbullet import AsyncPushbullet
from ..tmux import get_all_sessions
from ..device import _get_device_attr
from ..utils import get_api_key

# Session/device names to exclude from sync operations
EXCLUDED_NAMES = {"main"}


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="変更を行わず、実行内容のみ表示します。",
)
def auto_sync(dry_run):
    """
    tmuxセッションとPushbulletデバイスを同期します。

    - tmuxセッションが存在するがデバイスがない → デバイスを作成
    - デバイスが存在するがtmuxセッションがない → デバイスを削除

    デフォルトでは、push-tmuxが作成したデバイス（manufacturer="push-tmux"）のみが対象です。
    """

    async def _auto_sync():
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

                # Filter push-tmux devices
                push_tmux_devices = [
                    d
                    for d in devices
                    if _get_device_attr(d, "manufacturer") == "push-tmux"
                ]

                click.echo(f"\npush-tmuxが作成したデバイス ({len(push_tmux_devices)}件):")
                for device in push_tmux_devices:
                    click.echo(f"  - {_get_device_attr(device, 'nickname')}")

                existing_device_names = {
                    _get_device_attr(d, "nickname") for d in push_tmux_devices
                }

                # Check for excluded names
                excluded_sessions = [s for s in sessions if s in EXCLUDED_NAMES]
                excluded_devices = [
                    d for d in push_tmux_devices
                    if _get_device_attr(d, "nickname") in EXCLUDED_NAMES
                ]
                if excluded_sessions or excluded_devices:
                    click.echo(f"\n除外された項目 ({len(set(excluded_sessions) | {_get_device_attr(d, 'nickname') for d in excluded_devices})}件):")
                    for name in set(excluded_sessions) | {_get_device_attr(d, "nickname") for d in excluded_devices}:
                        if name in EXCLUDED_NAMES:
                            click.echo(f"  - {name} (同期をスキップ)")

                # Find sessions that need device creation
                # Exclude certain session names (e.g., "main")
                missing_sessions = [
                    s for s in sessions
                    if s not in existing_device_names and s not in EXCLUDED_NAMES
                ]

                # Find orphaned devices that need deletion
                # Exclude certain device names (e.g., "main")
                orphaned_devices = [
                    d
                    for d in push_tmux_devices
                    if _get_device_attr(d, "nickname") not in session_set
                    and _get_device_attr(d, "nickname") not in EXCLUDED_NAMES
                ]

                # Show summary
                click.echo("\n=== 同期計画 ===")
                if missing_sessions:
                    click.echo(f"\n作成するデバイス ({len(missing_sessions)}件):")
                    for session in missing_sessions:
                        click.echo(f"  + {session}")
                else:
                    click.echo("\n作成するデバイスはありません。")

                if orphaned_devices:
                    click.echo(f"\n削除するデバイス ({len(orphaned_devices)}件):")
                    for device in orphaned_devices:
                        device_name = _get_device_attr(device, "nickname")
                        device_id = _get_device_attr(device, "iden")
                        click.echo(f"  - {device_name} (ID: {device_id})")
                else:
                    click.echo("\n削除するデバイスはありません。")

                if not missing_sessions and not orphaned_devices:
                    click.echo("\ntmuxセッションとデバイスは既に同期しています。")
                    return

                if dry_run:
                    click.echo("\n[DRY RUN] 上記の変更を実行する準備ができています。")
                    return

                # Execute sync
                click.echo("\n同期を実行中...")
                created_count = 0
                create_failed_count = 0
                deleted_count = 0
                delete_failed_count = 0

                # Create missing devices
                if missing_sessions:
                    click.echo("\nデバイスを作成中...")
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
                            click.echo(
                                f"  ✗ デバイス '{session}' の作成に失敗しました: {e}",
                                err=True,
                            )
                            create_failed_count += 1

                # Delete orphaned devices
                if orphaned_devices:
                    click.echo("\nデバイスを削除中...")
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
                            delete_failed_count += 1

                click.echo(
                    f"\n完了: {created_count}件作成 ({create_failed_count}件失敗), "
                    f"{deleted_count}件削除 ({delete_failed_count}件失敗)"
                )

            except Exception as e:
                click.echo(f"エラーが発生しました: {e}", err=True)

    asyncio.run(_auto_sync())
