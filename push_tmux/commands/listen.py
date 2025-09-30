#!/usr/bin/env python3
"""
Listen command for push-tmux
"""

import asyncio
import click
import os
import aiohttp
from asyncpushbullet import AsyncPushbullet, LiveStreamListener
from typing import Dict, Any
from ..utils import get_api_key
from ..config import load_config, get_device_name
from ..device import (
    _resolve_target_device,
    _find_device_by_name_or_id,
    _resolve_specific_device,
    _resolve_default_device,
    _get_device_attr,
)
from ..tmux import send_to_tmux
from ..slash_commands import expand_slash_command, check_trigger_conditions
from ..triggers import check_triggers, process_trigger_actions
from ..builtin_commands import execute_builtin_command


def _get_source_device_name(devices, source_device_iden: str) -> str:
    """ソースデバイス名を取得"""
    if not source_device_iden:
        return "unknown"

    source_device = next(
        (d for d in devices if _get_device_attr(d, "iden") == source_device_iden),
        None,
    )
    return _get_device_attr(source_device, "nickname") if source_device else "unknown"


async def _process_message(
    message: str,
    config: Dict[str, Any],
    device_name: str,
    api_key: str,
    source_device_iden: str,
    source_device_name: str,
    is_auto_route: bool = False,
) -> None:
    """メッセージを処理（トリガー、ビルトインコマンド、スラッシュコマンド、通常メッセージ）"""
    # Check for triggers first
    trigger_actions = check_triggers(
        message, source_device_name or "unknown", config
    )
    if trigger_actions:
        await process_trigger_actions(trigger_actions, config)
        return

    # Check if it's a slash command
    from ..slash_commands import parse_slash_command

    # First parse the command
    command, arguments = parse_slash_command(message)

    if command:
        # Check if it's a built-in command
        is_builtin, result, error = await execute_builtin_command(
            command, arguments, config, api_key, source_device_iden,
            source_device_name
        )

        if is_builtin:
            # Built-in command handled
            if error:
                click.echo(f"Built-in command error: {error}", err=True)
            return

    # Not a built-in command, process as regular slash command
    is_slash, expanded_cmd, target_session, delay = (
        expand_slash_command(message, config, device_name)
    )

    if is_slash:
        if expanded_cmd and check_trigger_conditions(
            message.split()[0][1:], config
        ):
            # Execute the expanded command
            final_target = target_session or device_name

            if delay and delay > 0:
                # Execute asynchronously after delay
                asyncio.create_task(
                    delayed_execution(
                        delay,
                        config,
                        expanded_cmd,
                        final_target,
                        message.split()[0],
                    )
                )
                click.echo(
                    f"⏰ Timer set for {delay} seconds: {message.split()[0]}"
                )
            else:
                # Execute immediately
                await send_to_tmux(config, expanded_cmd, final_target)
                if is_auto_route:
                    click.echo(
                        f"Executed slash command: {message.split()[0]} for device '{device_name}'"
                    )
                else:
                    click.echo(f"Executed slash command: {message.split()[0]}")
        # else: command was rejected or had missing args, already handled by expand_slash_command
    else:
        # Regular message (or fallback from undefined slash command)
        await send_to_tmux(config, message, device_name)


async def delayed_execution(
    delay: int,
    config: Dict[str, Any],
    command: str,
    target: str,
    original_message: str = "",
) -> None:
    """
    Execute command after specified delay

    Args:
        delay: Seconds to wait
        config: Configuration dictionary
        command: Expanded command to execute
        target: Target tmux session
        original_message: Original slash command for logging
    """
    try:
        await asyncio.sleep(delay)
        await send_to_tmux(config, command, target)
        click.echo(
            f"⏰ Timer executed after {delay} seconds{f': {original_message}' if original_message else ''}"
        )
    except Exception as e:
        click.echo(f"Error in delayed execution: {e}", err=True)


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
        "tmux",
        "ls",
        "-F",
        "#{session_name}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await result.communicate()
    return stdout.decode().strip().split("\n") if stdout else []


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
            click.echo(
                f"  セッション '{session}' ← デバイス '{_get_device_attr(device, 'nickname')}'"
            )
        click.echo()
    else:
        click.echo("自動ルーティング対象のデバイスが見つかりません。")


def _create_auto_route_handler(api_key, config):
    """自動ルーティング用のハンドラーを作成"""

    async def on_push_auto_route(push):
        # noteタイプのみ処理
        if push.get("type") != "note":
            return

        target_device_iden = push.get("target_device_iden")
        if not target_device_iden:
            return

        # 対象デバイスの情報を取得
        async with AsyncPushbullet(api_key) as pb:
            devices = pb.get_devices()  # get_devicesは同期メソッド
            target_device = next(
                (
                    d
                    for d in devices
                    if _get_device_attr(d, "iden") == target_device_iden
                ),
                None,
            )

            if not target_device:
                return

            device_name = _get_device_attr(target_device, "nickname")
            if not device_name:
                return

            # Get source device name
            source_device_iden = push.get("source_device_iden", "")
            source_device_name = _get_source_device_name(devices, source_device_iden)

            # 同名のtmuxセッションが存在するかチェック
            from ..tmux import _check_session_exists

            if await _check_session_exists(device_name):
                message = push.get("body", "")
                if message:
                    await _process_message(
                        message,
                        config,
                        device_name,
                        api_key,
                        source_device_iden,
                        source_device_name,
                        is_auto_route=True,
                    )
            else:
                click.echo(f"対応するtmuxセッション '{device_name}' が見つかりません。")

    return on_push_auto_route


def _create_specific_device_handler(config, target_device_iden, device_name, api_key):
    """特定デバイス用のハンドラーを作成"""

    async def on_push(push):
        # noteタイプのみ処理
        if push.get("type") != "note":
            return

        push_target_device = push.get("target_device_iden")
        if not push_target_device:
            return

        # このデバイス宛のメッセージのみ処理
        if push_target_device != target_device_iden:
            return

        message = push.get("body", "")
        if message:
            # Get source device name
            source_device_iden = push.get("source_device_iden", "")
            source_device_name = "unknown"
            if source_device_iden and api_key:
                try:
                    async with AsyncPushbullet(api_key) as pb:
                        devices = pb.get_devices()
                        source_device_name = _get_source_device_name(devices, source_device_iden)
                except Exception:
                    pass

            await _process_message(
                message,
                config,
                device_name,
                api_key,
                source_device_iden,
                source_device_name,
                is_auto_route=False,
            )

    return on_push


async def _start_message_listener(api_key, on_push, debug):
    """メッセージリスナーを開始（自動再接続機能付き）"""
    retry_count = 0
    max_retries = -1  # 無限リトライ
    base_wait_time = 5  # 基本待機時間（秒）
    max_wait_time = 300  # 最大待機時間（5分）

    click.echo("リスナーを開始します...（Ctrl+Cで終了）")

    while max_retries < 0 or retry_count < max_retries:
        try:
            if retry_count > 0:
                # 指数バックオフで待機時間を増やす（最大5分まで）
                wait_time = min(base_wait_time * (2 ** min(retry_count - 1, 6)), max_wait_time)
                click.echo(f"WebSocket再接続を試みます... ({retry_count}回目, {wait_time}秒後)")
                await asyncio.sleep(wait_time)

            async with AsyncPushbullet(api_key) as pb:
                async with LiveStreamListener(pb) as listener:
                    if debug or retry_count > 0:
                        click.echo("WebSocketリスナーを開始しました")

                    if debug:
                        click.echo(f"[デバッグ] listener.closed: {listener.closed}")

                    # 接続成功時はリトライカウントをリセット
                    retry_count = 0

                    try:
                        while not listener.closed:
                            try:
                                push = await listener.next_push()
                                if push:
                                    await on_push(push)
                            except StopAsyncIteration as sie:
                                # next_pushからのStopAsyncIteration
                                if debug:
                                    click.echo(f"[デバッグ] StopAsyncIteration from next_push: {sie}")
                                break  # 内側のループを抜ける
                    except StopAsyncIteration as e:
                        # 外側のStopAsyncIteration（通常は発生しない）
                        if debug:
                            click.echo(f"[デバッグ] Outer StopAsyncIteration: {e}")
                        pass  # ループを抜けた後の処理へ

                    # 正常に閉じられた場合（StopAsyncIterationを発生させずに終了）
                    click.echo("WebSocket接続が閉じられました")
                    retry_count += 1  # 再接続を試行

        except aiohttp.ClientError as e:
            retry_count += 1
            click.echo(f"WebSocket接続エラー: {e}", err=True)
            # ネットワークエラーの場合は再試行を継続

        except asyncio.CancelledError:
            # タスクがキャンセルされた場合は終了
            click.echo("リスナーがキャンセルされました")
            break

        except StopAsyncIteration as e:
            # WebSocketのStopAsyncIterationはここでもキャッチ
            retry_count += 1
            error_msg = str(e) if str(e) else "Websocket closed"
            click.echo(f"WebSocket終了: {error_msg}")
            # 再接続を継続

        except Exception as e:
            retry_count += 1
            error_type = type(e).__name__
            click.echo(f"リスナーエラー ({error_type}): {e}", err=True)
            # その他のエラーも再試行

    if max_retries >= 0 and retry_count >= max_retries:
        click.echo(f"最大リトライ回数（{max_retries}）に達しました。リスナーを終了します。", err=True)


async def listen_main(device=None, all_devices=False, auto_route=False, debug=False):
    """メイン処理関数"""
    api_key = get_api_key()
    if not api_key:
        return

    config = load_config()
    target_device_iden, is_auto_route = await _resolve_target_device(
        api_key, device, all_devices, auto_route
    )

    on_push = await _create_push_handler(
        api_key, config, device, is_auto_route, target_device_iden
    )
    if not on_push:
        return

    await _start_message_listener(api_key, on_push, debug)


async def _create_push_handler(
    api_key, config, device, is_auto_route, target_device_iden
):
    """適切なプッシュハンドラーを作成"""
    if is_auto_route:
        return await _setup_auto_route_handler(api_key, config)
    elif target_device_iden:
        return await _setup_specific_device_handler(
            api_key, config, device, target_device_iden
        )
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
    target_device = (
        await _resolve_specific_device(api_key, device)
        if device
        else await _resolve_default_device(api_key)
    )
    device_name = (
        _get_device_attr(target_device, "nickname")
        if target_device
        else get_device_name()
    )
    click.echo(f"デバイス '{device_name}' のメッセージを待機します...")
    return _create_specific_device_handler(
        config, target_device_iden, device_name, api_key
    )


def _show_device_registration_message():
    """デバイス登録が必要なメッセージを表示"""
    click.echo("最初に `push-tmux register` でデバイスを登録してください。", err=True)


@click.command()
@click.option("--device", "-d", help="特定のデバイス名またはIDを指定")
@click.option("--all-devices", is_flag=True, help="全デバイスからのメッセージを受信")
@click.option(
    "--auto-route",
    is_flag=True,
    help="tmuxセッション名に基づいてメッセージを自動ルーティング",
)
@click.option(
    "--no-auto-route",
    is_flag=True,
    help="自動ルーティングを無効化（現在のデバイスのみ）",
)
@click.option("--debug", is_flag=True, help="デバッグ情報を表示")
def listen(device, all_devices, auto_route, no_auto_route, debug):
    """
    Pushbulletからのメッセージを待機し、tmuxに転送します。

    デフォルトでは自動ルーティングモードで動作し、すべてのデバイスのメッセージを
    対応するtmuxセッションに送信します。
    """
    # 引数がない場合は自動ルーティングをデフォルトに
    if not device and not all_devices and not auto_route and not no_auto_route:
        auto_route = True
        click.echo(
            "自動ルーティングモードで起動します（すべてのデバイスのメッセージを処理）"
        )

    # no_auto_route が指定された場合は auto_route を無効化
    if no_auto_route:
        auto_route = False

    asyncio.run(listen_main(device, all_devices, auto_route, debug))
