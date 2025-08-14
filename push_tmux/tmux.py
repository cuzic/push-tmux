#!/usr/bin/env python3
"""
tmux integration utilities for push-tmux
"""

import asyncio
import click
import os
from .device import _resolve_device_mapping


async def _check_session_exists(session_name):
    """tmuxセッションが存在するかチェック"""
    try:
        result = await asyncio.create_subprocess_exec(
            "tmux",
            "has-session",
            "-t",
            session_name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        returncode = await result.wait()
        return returncode == 0
    except Exception:
        return False


async def _get_current_session():
    """現在のtmuxセッション名を取得"""
    tmux_env = os.getenv("TMUX")
    if tmux_env:
        try:
            result = await asyncio.create_subprocess_exec(
                "tmux",
                "display-message",
                "-p",
                "#{session_name}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            if result.returncode == 0:
                return stdout.decode().strip()
        except Exception:
            pass
    return None


async def _try_mapped_session(device_name, device_mapping):
    """デバイスマッピングによるセッション解決を試行"""
    mapped_session, mapped_window, mapped_pane = await _resolve_device_mapping(
        device_name, device_mapping
    )

    if mapped_session and await _check_session_exists(mapped_session):
        click.echo(
            f"デバイス '{device_name}' のマッピング設定に従い、tmuxセッション '{mapped_session}' を使用します。"
        )
        return mapped_session, mapped_window, mapped_pane
    elif mapped_session:
        click.echo(
            f"警告: マッピングされたtmuxセッション '{mapped_session}' が存在しません。デフォルトに戻ります。"
        )

    return None, None, None


async def _try_device_name_session(device_name, device_mapping):
    """デバイス名と同名のセッション解決を試行"""
    if await _check_session_exists(device_name):
        click.echo(f"デバイス名と同じtmuxセッション '{device_name}' を使用します。")
        return device_name, None, None
    elif device_name not in device_mapping:
        click.echo(f"警告: tmuxセッション '{device_name}' が存在しません。")

    return None, None, None


async def _show_session_not_found_error(device_name):
    """セッションが見つからない場合のエラーメッセージ表示"""
    if device_name:
        click.echo(
            f"エラー: tmuxセッション '{device_name}' が見つかりません。", err=True
        )
        click.echo("以下のいずれかの対処を行ってください:", err=True)
        click.echo(f"  1. tmuxセッション '{device_name}' を作成する", err=True)
        click.echo(
            "  2. config.tomlの[device_mapping]セクションでマッピングを設定する",
            err=True,
        )
        click.echo(
            "  3. config.tomlの[tmux].default_target_sessionを設定する", err=True
        )
    else:
        click.echo("エラー: tmuxセッションが見つかりません。", err=True)
        click.echo(
            "`config.toml`で`[tmux].default_target_session`を設定してください。",
            err=True,
        )


async def _resolve_target_session(config, device_name):
    """ターゲットセッションを決定

    優先順位:
    1. device_mapping での明示的なマッピング
    2. use_device_name_as_session が true の場合、デバイス名と同じセッション
    3. default_target_session の設定
    4. 現在のtmuxセッション
    """
    session_config = _extract_session_config(config)

    # 優先順位に従って解決を試行
    result = await _try_priority_resolution(device_name, session_config)
    if result[0]:
        return result

    # フォールバック処理
    return await _handle_session_fallback(device_name, session_config)


def _extract_session_config(config):
    """セッション解決に必要な設定を抽出"""
    tmux_config = config.get("tmux", {})
    return {
        "default_session": tmux_config.get("default_target_session"),
        "use_device_name": tmux_config.get("use_device_name_as_session", True),
        "device_mapping": config.get("device_mapping", {}),
    }


async def _try_priority_resolution(device_name, session_config):
    """優先順位に従ってセッション解決を試行"""
    device_mapping = session_config["device_mapping"]

    # 1. device_mappingでの明示的なマッピングを最優先
    result = await _try_mapped_resolution(device_name, device_mapping)
    if result[0]:
        return result

    # 2. デバイス名と同じセッション
    return await _try_device_name_resolution(device_name, session_config)


async def _try_mapped_resolution(device_name, device_mapping):
    """マッピングによる解決を試行"""
    if device_name and device_name in device_mapping:
        result = await _try_mapped_session(device_name, device_mapping)
        if result[0]:
            return result
    return None, None, None


async def _try_device_name_resolution(device_name, session_config):
    """デバイス名による解決を試行"""
    if device_name and session_config["use_device_name"]:
        result = await _try_device_name_session(
            device_name, session_config["device_mapping"]
        )
        if result[0]:
            return result
    return None, None, None


async def _handle_session_fallback(device_name, session_config):
    """フォールバック処理 - デフォルトセッション・現在セッション"""
    # デフォルトセッションを試行
    result = await _try_default_session(session_config["default_session"])
    if result[0]:
        return result

    # 現在のセッションを試行
    result = await _try_current_session()
    if result[0]:
        return result

    # エラー処理
    await _show_session_not_found_error(device_name)
    return None, None, None


async def _try_default_session(default_session):
    """デフォルトセッションの解決を試行"""
    if default_session and default_session != "current":
        if await _check_session_exists(default_session):
            click.echo(f"デフォルトのtmuxセッション '{default_session}' を使用します。")
            return default_session, None, None
        else:
            click.echo(
                f"警告: デフォルトセッション '{default_session}' が存在しません。"
            )
    return None, None, None


async def _try_current_session():
    """現在のセッションの解決を試行"""
    current_session = await _get_current_session()
    if current_session:
        click.echo(f"現在のtmuxセッション '{current_session}' を使用します。")
        return current_session, None, None
    return None, None, None


async def _resolve_first_window(target_session):
    """最初のウィンドウを取得"""
    try:
        result = await asyncio.create_subprocess_exec(
            "tmux",
            "list-windows",
            "-t",
            target_session,
            "-F",
            "#{window_index}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await result.communicate()
        windows = stdout.decode().strip().split("\n")
        return windows[0] if windows else "0"
    except Exception:
        return "0"


async def _resolve_first_pane(target_session, target_window):
    """最初のペインを取得"""
    try:
        result = await asyncio.create_subprocess_exec(
            "tmux",
            "list-panes",
            "-t",
            f"{target_session}:{target_window}",
            "-F",
            "#{pane_index}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await result.communicate()
        panes = stdout.decode().strip().split("\n")
        return panes[0] if panes else "0"
    except Exception:
        return "0"


async def _apply_mapping_overrides(
    window_setting, pane_setting, mapped_window, mapped_pane
):
    """マッピングのオーバーライドを適用"""
    if mapped_window is not None:
        window_setting = mapped_window
    if mapped_pane is not None:
        pane_setting = mapped_pane
    return window_setting, pane_setting


async def _resolve_window_pane(
    target_session, window_setting, pane_setting, mapped_window, mapped_pane
):
    """ウィンドウとペインの設定を解決"""
    # マッピングで指定されたウィンドウ・ペインがあれば使用
    window_setting, pane_setting = await _apply_mapping_overrides(
        window_setting, pane_setting, mapped_window, mapped_pane
    )

    # デフォルト値の設定
    if window_setting is None:
        window_setting = "first"
    if pane_setting is None:
        pane_setting = "first"

    # ウィンドウ設定の処理
    if window_setting == "first":
        target_window = await _resolve_first_window(target_session)
    else:
        target_window = window_setting

    # ペイン設定の処理
    if pane_setting == "first":
        target_pane = await _resolve_first_pane(target_session, target_window)
    else:
        target_pane = pane_setting

    return target_window, target_pane


async def _send_tmux_commands(target, message, enter_delay=0.5):
    """tmuxにメッセージとEnterキーを送信"""
    try:
        # メッセージを送信
        click.echo(f"tmuxセッション '{target}' にメッセージを送信します...")

        # まずメッセージを送信（Enterなし）
        await asyncio.create_subprocess_exec("tmux", "send-keys", "-t", target, message)

        # 少し待機（アプリケーションがテキストを処理する時間を確保）
        await asyncio.sleep(enter_delay)

        # Enterキーを送信
        await asyncio.create_subprocess_exec("tmux", "send-keys", "-t", target, "Enter")

        click.echo(f"メッセージ '{message}' を送信しました。")
    except Exception as e:
        click.echo(f"tmuxへの送信でエラーが発生しました: {e}", err=True)


async def send_to_tmux(config, message, device_name=None):
    """tmuxにメッセージを送信するメイン関数"""
    # セッションの決定
    target_session, mapped_window, mapped_pane = await _resolve_target_session(
        config, device_name
    )
    if not target_session:
        return

    # ウィンドウとペインの決定
    tmux_config = config.get("tmux", {})
    window_setting = tmux_config.get("target_window")
    pane_setting = tmux_config.get("target_pane")

    target_window, target_pane = await _resolve_window_pane(
        target_session, window_setting, pane_setting, mapped_window, mapped_pane
    )

    # tmux送信先を構築
    target = f"{target_session}:{target_window}.{target_pane}"

    # Enter送信前の遅延時間を設定から取得（デフォルト0.5秒）
    enter_delay = tmux_config.get("enter_delay", 0.5)

    # tmuxにコマンド送信
    await _send_tmux_commands(target, message, enter_delay)
