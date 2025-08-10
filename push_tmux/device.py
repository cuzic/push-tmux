#!/usr/bin/env python3
"""
Device resolution utilities for push-tmux
"""
import click
from asyncpushbullet import AsyncPushbullet
from .config import get_device_name


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


def _get_device_attr(device, attr):
    """デバイスオブジェクトまたはdictから属性を取得"""
    # Deviceオブジェクトの場合
    if hasattr(device, attr):
        return getattr(device, attr)
    # dictの場合
    elif isinstance(device, dict):
        return device.get(attr)
    return None


def _find_target_device(devices, name, device_id):
    """デバイス一覧からターゲットデバイスを検索"""
    for device in devices:
        device_iden = _get_device_attr(device, 'iden')
        device_nickname = _get_device_attr(device, 'nickname')
        
        if device_id and device_iden == device_id:
            return device
        elif name and device_nickname == name:
            return device
    return None


async def _find_device_by_name_or_id(devices, search_term):
    """名前またはIDでデバイスを検索"""
    for device in devices:
        device_iden = _get_device_attr(device, 'iden')
        device_nickname = _get_device_attr(device, 'nickname')
        
        if (device_nickname == search_term or device_iden == search_term):
            return device
    return None


async def _resolve_specific_device(api_key, device):
    """特定のデバイスを解決"""
    async with AsyncPushbullet(api_key) as pb:
        devices = pb.get_devices()  # get_devicesは同期メソッド
        return await _find_device_by_name_or_id(devices, device)


async def _resolve_default_device(api_key):
    """デフォルトデバイスを解決"""
    device_name = get_device_name()
    async with AsyncPushbullet(api_key) as pb:
        devices = pb.get_devices()  # get_devicesは同期メソッド
        return await _find_device_by_name_or_id(devices, device_name)


async def _resolve_target_device(api_key, device, all_devices, auto_route):
    """ターゲットデバイスを解決"""
    if auto_route:
        # 自動ルーティングモードでは全デバイス対象
        return None, True  # device_iden=None, auto_route=True
    
    if all_devices:
        # 全デバイスモード
        return None, False  # device_iden=None, auto_route=False
    
    # 特定デバイスモード
    if device:
        target_device = await _resolve_specific_device(api_key, device)
    else:
        target_device = await _resolve_default_device(api_key)
    
    if not target_device:
        device_name = device or get_device_name()
        click.echo(f"エラー: デバイス '{device_name}' が見つかりません。", err=True)
        return None, False
    
    return _get_device_attr(target_device, 'iden'), False