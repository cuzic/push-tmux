#!/usr/bin/env python3
"""
Device deletion command for push-tmux
"""

import asyncio
import click
import os
from datetime import datetime
from asyncpushbullet import AsyncPushbullet
import questionary
from ..device import _find_target_device, _get_device_attr
from ..utils import get_api_key


def _format_created_time(created):
    """作成時刻を読みやすい形式にフォーマット"""
    try:
        return datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return str(created)


def _create_device_choice(device):
    """デバイス選択肢を作成"""
    name = _get_device_attr(device, "nickname") or "N/A"
    status = "✓" if (_get_device_attr(device, "active") is not False) else "✗"
    created = _format_created_time(_get_device_attr(device, "created") or 0)
    device_iden = _get_device_attr(device, "iden")
    return f"{status} {name} (ID: {device_iden[:8] if device_iden else 'N/A'}...) - {created}"


async def _delete_single_device(api_key, name, device_id, yes):
    """単一デバイスの削除"""
    async with AsyncPushbullet(api_key) as pb:
        try:
            devices = pb.get_devices()  # get_devicesは同期メソッド
            target_device = _find_target_device(devices, name, device_id)

            if not target_device:
                _show_device_not_found_error(device_id, name)
                return

            if not _should_delete_device(target_device, yes):
                return

            await _execute_device_deletion(pb, target_device)

        except Exception as e:
            click.echo(f"デバイス削除中にエラーが発生しました: {e}", err=True)


def _show_device_not_found_error(device_id, name):
    """デバイスが見つからないエラーを表示"""
    if device_id:
        click.echo(f"エラー: ID '{device_id}' のデバイスが見つかりません。", err=True)
    else:
        click.echo(f"エラー: 名前 '{name}' のデバイスが見つかりません。", err=True)


def _should_delete_device(target_device, yes):
    """デバイスを削除するかどうか確認"""
    if yes:
        return True

    click.echo("\nデバイス情報:")
    click.echo(f"  名前: {_get_device_attr(target_device, 'nickname') or 'N/A'}")
    click.echo(f"  ID: {_get_device_attr(target_device, 'iden')}")
    click.echo(f"  作成日時: {_get_device_attr(target_device, 'created') or 'N/A'}")

    if not click.confirm("\nこのデバイスを削除しますか？"):
        click.echo("削除をキャンセルしました。")
        return False
    return True


async def _execute_device_deletion(pb, target_device):
    """デバイス削除を実行"""
    device_iden = _get_device_attr(target_device, "iden")
    await pb.async_remove_device(target_device)
    click.echo(
        f"デバイス '{_get_device_attr(target_device, 'nickname') or 'N/A'}' (ID: {device_iden}) を削除しました。"
    )


async def _select_devices_for_deletion(devices):
    """削除対象デバイスを選択"""
    if not devices:
        click.echo("削除可能なデバイスがありません。")
        return []

    choices = [_create_device_choice(device) for device in devices]
    selected = questionary.checkbox(
        "削除するデバイスを選択してください:", choices=choices
    ).ask()

    return [devices[choices.index(choice)] for choice in selected] if selected else []


async def _confirm_deletion(selected_devices):
    """削除の最終確認"""
    click.echo(f"\n{len(selected_devices)}個のデバイスを削除します:")
    for device in selected_devices:
        device_iden = _get_device_attr(device, "iden")
        click.echo(
            f"  - {_get_device_attr(device, 'nickname') or 'N/A'} (ID: {device_iden[:8] if device_iden else 'N/A'}...)"
        )

    return click.confirm(f"\n本当に{len(selected_devices)}個のデバイスを削除しますか？")


async def _delete_multiple_devices(pb, selected_devices):
    """複数デバイスの削除実行"""
    success_count = 0
    for device in selected_devices:
        try:
            await pb.async_remove_device(device)
            click.echo(
                f"✓ {_get_device_attr(device, 'nickname') or 'N/A'} を削除しました"
            )
            success_count += 1
        except Exception as e:
            click.echo(
                f"✗ {_get_device_attr(device, 'nickname') or 'N/A'} の削除に失敗: {e}"
            )

    click.echo(
        f"\n{success_count}/{len(selected_devices)} 個のデバイスを削除しました。"
    )


async def _delete_devices_interactive(api_key, include_inactive):
    """インタラクティブなデバイス削除"""
    async with AsyncPushbullet(api_key) as pb:
        try:
            all_devices = pb.get_devices()  # get_devicesは同期メソッド

            devices = _filter_devices_by_status(all_devices, include_inactive)

            if not devices:
                _show_no_devices_message(include_inactive)
                return

            selected_devices = await _select_devices_for_deletion(devices)
            if not selected_devices:
                click.echo("削除対象が選択されませんでした。")
                return

            await _handle_batch_deletion(pb, selected_devices)

        except Exception as e:
            click.echo(f"デバイス削除中にエラーが発生しました: {e}", err=True)


def _filter_devices_by_status(all_devices, include_inactive):
    """アクティブステータスによってデバイスをフィルター"""
    if include_inactive:
        return all_devices
    else:
        return [d for d in all_devices if _get_device_attr(d, "active") is not False]


def _show_no_devices_message(include_inactive):
    """デバイスがない場合のメッセージを表示"""
    if include_inactive:
        click.echo("削除可能なデバイスがありません。")
    else:
        click.echo(
            "アクティブなデバイスがありません。--include-inactiveオプションで非アクティブデバイスも含められます。"
        )


async def _handle_batch_deletion(pb, selected_devices):
    """バッチ削除を処理"""
    if await _confirm_deletion(selected_devices):
        await _delete_multiple_devices(pb, selected_devices)
    else:
        click.echo("削除をキャンセルしました。")


@click.option("--name", help="削除するデバイス名")
@click.option("--id", "device_id", help="削除するデバイスID")
@click.option("--yes", "-y", is_flag=True, help="削除確認をスキップ")
@click.option("--include-inactive", is_flag=True, help="非アクティブデバイスも含める")
def delete_devices(name, device_id, yes, include_inactive):
    """
    Pushbulletデバイスを削除します。
    --nameまたは--idオプションで特定デバイスを指定、未指定時はインタラクティブ選択。
    """

    async def _delete_devices():
        api_key = get_api_key()
        if not api_key:
            return

        # 単一削除モード（--nameまたは--id指定時）
        if name or device_id:
            await _delete_single_device(api_key, name, device_id, yes)
        else:
            # 複数選択削除モード
            await _delete_devices_interactive(api_key, include_inactive)

    asyncio.run(_delete_devices())
