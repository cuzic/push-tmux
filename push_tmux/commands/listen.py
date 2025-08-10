#!/usr/bin/env python3
"""
Listen command for push-tmux
"""
import asyncio
import click
import os
import aiohttp
from asyncpushbullet import AsyncPushbullet, LiveStreamListener
from ..config import load_config, get_device_name
from ..device import _resolve_target_device, _find_device_by_name_or_id, _resolve_specific_device, _resolve_default_device, _get_device_attr
from ..tmux import send_to_tmux


async def _display_auto_route_devices(api_key):
    """自動ルーティング対象デバイスを表示"""
    async with AsyncPushbullet(api_key) as pb:
        try:
            result = await asyncio.create_subprocess_exec(
                'tmux', 'ls', '-F', '#{session_name}',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            sessions = stdout.decode().strip().split('\n') if stdout else []
            
            if not sessions:
                click.echo("tmuxセッションが見つかりません。")
                return
            
            devices = pb.get_devices()  # get_devicesは同期メソッド
            matching_devices = []
            
            for session in sessions:
                device = await _find_device_by_name_or_id(devices, session)
                if device:
                    matching_devices.append((session, device))
            
            if matching_devices:
                click.echo("自動ルーティング対象:")
                for session, device in matching_devices:
                    click.echo(f"  セッション '{session}' ← デバイス '{_get_device_attr(device, 'nickname')}'")
                click.echo()
            else:
                click.echo("自動ルーティング対象のデバイスが見つかりません。")
                
        except Exception as e:
            click.echo(f"セッション情報取得エラー: {e}")


def _create_auto_route_handler(api_key, config):
    """自動ルーティング用のハンドラーを作成"""
    
    async def on_push_auto_route(push):
        # noteタイプのみ処理
        if push.get('type') != 'note':
            return
            
        target_device_iden = push.get('target_device_iden')
        if not target_device_iden:
            return
        
        # 対象デバイスの情報を取得
        async with AsyncPushbullet(api_key) as pb:
            devices = pb.get_devices()  # get_devicesは同期メソッド
            target_device = next((d for d in devices if _get_device_attr(d, 'iden') == target_device_iden), None)
            
            if not target_device:
                return
            
            device_name = _get_device_attr(target_device, 'nickname')
            if not device_name:
                return
            
            # 同名のtmuxセッションが存在するかチェック
            from ..tmux import _check_session_exists
            if await _check_session_exists(device_name):
                message = push.get('body', '')
                if message:
                    await send_to_tmux(config, message, device_name)
            else:
                click.echo(f"対応するtmuxセッション '{device_name}' が見つかりません。")
    
    return on_push_auto_route


def _create_specific_device_handler(config, target_device_iden, device_name):
    """特定デバイス用のハンドラーを作成"""
    async def on_push(push):
        # noteタイプのみ処理
        if push.get('type') != 'note':
            return
            
        push_target_device = push.get('target_device_iden')
        if not push_target_device:
            return
        
        # このデバイス宛のメッセージのみ処理
        if push_target_device != target_device_iden:
            return
        
        message = push.get('body', '')
        if message:
            await send_to_tmux(config, message, device_name)
    
    return on_push


async def _start_message_listener(api_key, on_push, debug):
    """メッセージリスナーを開始"""
    try:
        async with AsyncPushbullet(api_key) as pb:
            async with LiveStreamListener(pb) as listener:
                if debug:
                    click.echo("WebSocketリスナーを開始します...")
                while not listener.closed:
                    push = await listener.next_push()
                    if push:
                        await on_push(push)
    except aiohttp.ClientError as e:
        click.echo(f"WebSocket接続エラー: {e}", err=True)
    except Exception as e:
        click.echo(f"リスナーエラー: {e}", err=True)


async def listen_main(device=None, all_devices=False, auto_route=False, debug=False):
    """メイン処理関数"""
    api_key = os.getenv('PUSHBULLET_TOKEN')
    if not api_key:
        click.echo("エラー: PUSHBULLET_TOKEN環境変数が設定されていません。", err=True)
        return
    
    config = load_config()
    target_device_iden, is_auto_route = await _resolve_target_device(api_key, device, all_devices, auto_route)
    
    if is_auto_route:
        click.echo("自動ルーティングモードで開始します。")
        await _display_auto_route_devices(api_key)
        on_push = _create_auto_route_handler(api_key, config)
    elif target_device_iden:
        # 特定デバイスモード
        target_device = await _resolve_specific_device(api_key, device) if device else await _resolve_default_device(api_key)
        device_name = _get_device_attr(target_device, 'nickname') if target_device else get_device_name()
        click.echo(f"デバイス '{device_name}' のメッセージを待機します...")
        on_push = _create_specific_device_handler(config, target_device_iden, device_name)
    else:
        return
    
    await _start_message_listener(api_key, on_push, debug)


@click.command()
@click.option('--device', '-d', help='特定のデバイス名またはIDを指定')
@click.option('--all-devices', is_flag=True, help='全デバイスからのメッセージを受信')
@click.option('--auto-route', is_flag=True, help='tmuxセッション名に基づいてメッセージを自動ルーティング')
@click.option('--debug', is_flag=True, help='デバッグ情報を表示')
def listen(device, all_devices, auto_route, debug):
    """
    Pushbulletからのメッセージを待機し、tmuxに転送します。
    """
    asyncio.run(listen_main(device, all_devices, auto_route, debug))