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
            sessions = await _get_tmux_sessions()
            if not sessions:
                click.echo("tmuxセッションが見つかりません。")
                return
            
            devices = pb.get_devices()  # get_devicesは同期メソッド
            matching_devices = await _find_matching_devices(devices, sessions)
            
            _display_matching_results(matching_devices)
                
        except Exception as e:
            click.echo(f"セッション情報取得エラー: {e}")


async def _get_tmux_sessions():
    """現在のtmuxセッション一覧を取得"""
    result = await asyncio.create_subprocess_exec(
        'tmux', 'ls', '-F', '#{session_name}',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await result.communicate()
    return stdout.decode().strip().split('\n') if stdout else []


async def _find_matching_devices(devices, sessions):
    """セッションに対応するデバイスを検索"""
    matching_devices = []
    for session in sessions:
        device = await _find_device_by_name_or_id(devices, session)
        if device:
            matching_devices.append((session, device))
    return matching_devices


def _display_matching_results(matching_devices):
    """マッチング結果を表示"""
    if matching_devices:
        click.echo("自動ルーティング対象:")
        for session, device in matching_devices:
            click.echo(f"  セッション '{session}' ← デバイス '{_get_device_attr(device, 'nickname')}'")
        click.echo()
    else:
        click.echo("自動ルーティング対象のデバイスが見つかりません。")


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
    
    on_push = await _create_push_handler(api_key, config, device, is_auto_route, target_device_iden)
    if not on_push:
        return
    
    await _start_message_listener(api_key, on_push, debug)


async def _create_push_handler(api_key, config, device, is_auto_route, target_device_iden):
    """適切なプッシュハンドラーを作成"""
    if is_auto_route:
        return await _setup_auto_route_handler(api_key, config)
    elif target_device_iden:
        return await _setup_specific_device_handler(api_key, config, device, target_device_iden)
    else:
        _show_device_registration_message()
        return None


async def _setup_auto_route_handler(api_key, config):
    """自動ルーティングハンドラーを設定"""
    click.echo("自動ルーティングモードで開始します。")
    await _display_auto_route_devices(api_key)
    return _create_auto_route_handler(api_key, config)


async def _setup_specific_device_handler(api_key, config, device, target_device_iden):
    """特定デバイスハンドラーを設定"""
    target_device = await _resolve_specific_device(api_key, device) if device else await _resolve_default_device(api_key)
    device_name = _get_device_attr(target_device, 'nickname') if target_device else get_device_name()
    click.echo(f"デバイス '{device_name}' のメッセージを待機します...")
    return _create_specific_device_handler(config, target_device_iden, device_name)


def _show_device_registration_message():
    """デバイス登録が必要なメッセージを表示"""
    click.echo("最初に `push-tmux register` でデバイスを登録してください。", err=True)


@click.command()
@click.option('--device', '-d', help='特定のデバイス名またはIDを指定')
@click.option('--all-devices', is_flag=True, help='全デバイスからのメッセージを受信')
@click.option('--auto-route', is_flag=True, help='tmuxセッション名に基づいてメッセージを自動ルーティング')
@click.option('--no-auto-route', is_flag=True, help='自動ルーティングを無効化（現在のデバイスのみ）')
@click.option('--debug', is_flag=True, help='デバッグ情報を表示')
def listen(device, all_devices, auto_route, no_auto_route, debug):
    """
    Pushbulletからのメッセージを待機し、tmuxに転送します。
    
    デフォルトでは自動ルーティングモードで動作し、すべてのデバイスのメッセージを
    対応するtmuxセッションに送信します。
    """
    # 引数がない場合は自動ルーティングをデフォルトに
    if not device and not all_devices and not auto_route and not no_auto_route:
        auto_route = True
        click.echo("自動ルーティングモードで起動します（すべてのデバイスのメッセージを処理）")
    
    # no_auto_route が指定された場合は auto_route を無効化
    if no_auto_route:
        auto_route = False
    
    asyncio.run(listen_main(device, all_devices, auto_route, debug))