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
from ..device import _find_target_device


def _format_created_time(created):
    """作成時刻を読みやすい形式にフォーマット"""
    try:
        return datetime.fromtimestamp(created).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return str(created)


def _create_device_choice(device):
    """デバイス選択肢を作成"""
    name = device.get('nickname', 'N/A')
    status = '✓' if device.get('active', True) else '✗'
    created = _format_created_time(device.get('created', 0))
    return f"{status} {name} (ID: {device['iden'][:8]}...) - {created}"


async def _delete_single_device(api_key, name, device_id, yes):
    """単一デバイスの削除"""
    async with AsyncPushbullet(api_key) as pb:
        try:
            devices = await pb.get_devices()
            target_device = _find_target_device(devices, name, device_id)
            
            if not target_device:
                if device_id:
                    click.echo(f"エラー: ID '{device_id}' のデバイスが見つかりません。", err=True)
                else:
                    click.echo(f"エラー: 名前 '{name}' のデバイスが見つかりません。", err=True)
                return
            
            # 削除確認
            if not yes:
                click.echo(f"\nデバイス情報:")
                click.echo(f"  名前: {target_device.get('nickname', 'N/A')}")
                click.echo(f"  ID: {target_device['iden']}")
                click.echo(f"  作成日時: {target_device.get('created', 'N/A')}")
                
                if not click.confirm("\nこのデバイスを削除しますか？"):
                    click.echo("削除をキャンセルしました。")
                    return
            
            # デバイス削除実行
            await pb.delete_device(target_device['iden'])
            click.echo(f"デバイス '{target_device.get('nickname', 'N/A')}' (ID: {target_device['iden']}) を削除しました。")
            
        except Exception as e:
            click.echo(f"デバイス削除中にエラーが発生しました: {e}", err=True)


async def _select_devices_for_deletion(devices):
    """削除対象デバイスを選択"""
    if not devices:
        click.echo("削除可能なデバイスがありません。")
        return []
    
    choices = [_create_device_choice(device) for device in devices]
    selected = questionary.checkbox(
        "削除するデバイスを選択してください:",
        choices=choices
    ).ask()
    
    return [devices[choices.index(choice)] for choice in selected] if selected else []


async def _confirm_deletion(selected_devices):
    """削除の最終確認"""
    click.echo(f"\n{len(selected_devices)}個のデバイスを削除します:")
    for device in selected_devices:
        click.echo(f"  - {device.get('nickname', 'N/A')} (ID: {device['iden'][:8]}...)")
    
    return click.confirm(f"\n本当に{len(selected_devices)}個のデバイスを削除しますか？")


async def _delete_multiple_devices(pb, selected_devices):
    """複数デバイスの削除実行"""
    success_count = 0
    for device in selected_devices:
        try:
            await pb.delete_device(device['iden'])
            click.echo(f"✓ {device.get('nickname', 'N/A')} を削除しました")
            success_count += 1
        except Exception as e:
            click.echo(f"✗ {device.get('nickname', 'N/A')} の削除に失敗: {e}")
    
    click.echo(f"\n{success_count}/{len(selected_devices)} 個のデバイスを削除しました。")


async def _delete_devices_interactive(api_key, include_inactive):
    """インタラクティブなデバイス削除"""
    async with AsyncPushbullet(api_key) as pb:
        try:
            all_devices = await pb.get_devices()
            
            if include_inactive:
                devices = all_devices
            else:
                devices = [d for d in all_devices if d.get('active', True)]
            
            if not devices:
                if include_inactive:
                    click.echo("削除可能なデバイスがありません。")
                else:
                    click.echo("アクティブなデバイスがありません。--include-inactiveオプションで非アクティブデバイスも含められます。")
                return
            
            selected_devices = await _select_devices_for_deletion(devices)
            if not selected_devices:
                click.echo("削除対象が選択されませんでした。")
                return
            
            if await _confirm_deletion(selected_devices):
                await _delete_multiple_devices(pb, selected_devices)
            else:
                click.echo("削除をキャンセルしました。")
                
        except Exception as e:
            click.echo(f"デバイス削除中にエラーが発生しました: {e}", err=True)


@click.command('delete-devices')
@click.option('--name', help='削除するデバイス名')
@click.option('--id', 'device_id', help='削除するデバイスID')
@click.option('--yes', '-y', is_flag=True, help='削除確認をスキップ')
@click.option('--include-inactive', is_flag=True, help='非アクティブデバイスも含める')
def delete_devices(name, device_id, yes, include_inactive):
    """
    Pushbulletデバイスを削除します。
    --nameまたは--idオプションで特定デバイスを指定、未指定時はインタラクティブ選択。
    """
    async def _delete_devices():
        api_key = os.getenv('PUSHBULLET_TOKEN')
        if not api_key:
            click.echo("エラー: PUSHBULLET_TOKEN環境変数が設定されていません。", err=True)
            return
        
        # 単一削除モード（--nameまたは--id指定時）
        if name or device_id:
            await _delete_single_device(api_key, name, device_id, yes)
        else:
            # 複数選択削除モード
            await _delete_devices_interactive(api_key, include_inactive)
    
    asyncio.run(_delete_devices())