#!/usr/bin/env python3
"""
Device resolution utilities for push-tmux
"""
import asyncio
import click
from asyncpushbullet import AsyncPushbullet


async def _resolve_device_mapping(device_name, device_mapping):
    """デバイスマッピング設定を解決"""
    if device_name in device_mapping:
        mapping = device_mapping[device_name]
        if isinstance(mapping, str):
            return mapping, None, None
        elif isinstance(mapping, dict):
            session = mapping.get('session')
            window = mapping.get('window')
            pane = mapping.get('pane')
            return session, window, pane
    return None, None, None


def _find_target_device(devices, name, device_id):
    """デバイス一覧からターゲットデバイスを検索"""
    for device in devices:
        if device_id and device['iden'] == device_id:
            return device
        elif name and device.get('nickname') == name:
            return device
    return None


async def _find_device_by_name_or_id(devices, search_term):
    """名前またはIDでデバイスを検索"""
    for device in devices:
        if (device.get('nickname') == search_term or 
            device['iden'] == search_term):
            return device
    return None


async def _resolve_specific_device(api_key, device):
    """特定のデバイスを解決"""
    async with AsyncPushbullet(api_key) as pb:
        devices = await pb.get_devices()
        return await _find_device_by_name_or_id(devices, device)


async def _resolve_default_device(api_key):
    """デフォルトデバイスを解決"""
    from .config import get_device_name
    
    device_name = get_device_name()
    async with AsyncPushbullet(api_key) as pb:
        devices = await pb.get_devices()
        return await _find_device_by_name_or_id(devices, device_name)


async def _resolve_target_device(api_key, device, all_devices, auto_route):
    """ターゲットデバイスを解決"""
    if auto_route:
        # 自動ルーティングモードでは全デバイス対象
        return None, True  # device_iden=None, auto_route=True
    elif all_devices:
        # 全デバイスモード
        return None, False  # device_iden=None, auto_route=False
    elif device:
        # 特定のデバイス指定
        target_device = await _resolve_specific_device(api_key, device)
        if not target_device:
            click.echo(f"エラー: デバイス '{device}' が見つかりません。", err=True)
            return None, False
        device_name = target_device.get('nickname', device)
        return target_device['iden'], False
    else:
        # デフォルトデバイス
        target_device = await _resolve_default_device(api_key)
        if not target_device:
            from .config import get_device_name
            device_name = get_device_name()
            click.echo(f"エラー: デバイス '{device_name}' が見つかりません。", err=True)
            click.echo("最初に `push-tmux register` でデバイスを登録してください。", err=True)
            return None, False
        device_name = target_device.get('nickname')
        return target_device['iden'], False