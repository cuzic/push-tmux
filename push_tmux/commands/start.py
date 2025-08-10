#!/usr/bin/env python3
"""
Unified start command for push-tmux (combines listen and daemon functionality)
"""
import asyncio
import click
import os
import sys
import signal
import time
import subprocess
from pathlib import Path
from ..config import load_config
from ..logging import setup_logging, log_daemon_event
from .listen import listen_main


@click.command()
@click.option('--device', '-d', help='特定のデバイス名またはIDを指定')
@click.option('--all-devices', is_flag=True, help='全デバイスからのメッセージを受信')  
@click.option('--auto-route', is_flag=True, help='tmuxセッション名に基づいてメッセージを自動ルーティング')
@click.option('--no-auto-route', is_flag=True, help='自動ルーティングを無効化（現在のデバイスのみ）')
@click.option('--daemon', is_flag=True, help='デーモンモード（ファイル変更監視とホットリロード）')
@click.option('--once', is_flag=True, help='一回限りのメッセージ待機（デーモンモードと排他）')
@click.option('--debug', is_flag=True, help='デバッグ情報を表示')
@click.option('--reload-interval', type=float, default=1.0, help='ファイル変更監視間隔（秒、デーモンモード時のみ）')
@click.option('--watch-files', multiple=True, help='監視するファイル（複数指定可能、デーモンモード時のみ）')
def start(device, all_devices, auto_route, no_auto_route, daemon, once, debug, reload_interval, watch_files):
    """
    Pushbulletからのメッセージを待機し、tmuxに転送します。
    
    デフォルトでは自動ルーティングモードで継続的に動作し、全デバイスのメッセージを
    対応するtmuxセッションに送信します。
    
    --onceオプションで一回限りの実行、--daemonオプションでファイル監視付きの
    デーモンモードを選択できます。
    """
    # 引数の検証
    if daemon and once:
        click.echo("エラー: --daemon と --once は同時に指定できません。", err=True)
        return
    
    # 引数がない場合は自動ルーティングをデフォルトに
    if not device and not all_devices and not auto_route and not no_auto_route:
        auto_route = True
        
    # no_auto_route が指定された場合は auto_route を無効化
    if no_auto_route:
        auto_route = False
    
    config = load_config()
    
    if daemon:
        # デーモンモード - ファイル監視とホットリロード機能
        _run_daemon_mode(config, device, all_devices, auto_route, debug, reload_interval, watch_files)
    elif once:
        # 一回限りモード - 単発のメッセージ待機
        _run_once_mode(config, device, all_devices, auto_route, debug)
    else:
        # デフォルト - 継続的なメッセージ待機（シンプル）
        _run_continuous_mode(config, device, all_devices, auto_route, debug)


def _run_daemon_mode(config, device, all_devices, auto_route, debug, reload_interval, watch_files):
    """デーモンモード - ファイル変更監視付き"""
    setup_logging(config, is_daemon=True)
    
    # デフォルトの監視ファイル設定
    daemon_config = config.get('daemon', {})
    default_watch_files = daemon_config.get('watch_files', ['config.toml', '.env'])
    actual_watch_files = list(watch_files) if watch_files else default_watch_files
    actual_reload_interval = reload_interval if reload_interval != 1.0 else daemon_config.get('reload_interval', 1.0)
    
    mode_desc = "自動ルーティング" if auto_route else (device or 'default')
    click.echo(f"デーモンモード開始 - モード: {mode_desc}")
    click.echo(f"監視ファイル: {actual_watch_files}")
    click.echo(f"監視間隔: {actual_reload_interval}秒")
    
    log_daemon_event("DAEMON_START", {
        "mode": mode_desc,
        "watch_files": actual_watch_files,
        "reload_interval": actual_reload_interval
    })
    
    # ファイルのタイムスタンプを記録
    file_timestamps = {}
    for filepath in actual_watch_files:
        if Path(filepath).exists():
            file_timestamps[filepath] = Path(filepath).stat().st_mtime
    
    def signal_handler(signum, frame):
        click.echo("\nデーモンを停止しています...")
        log_daemon_event("DAEMON_STOP", {"signal": signum})
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # メインループ
    try:
        while True:
            # ファイルの変更をチェック
            reload_needed = False
            for filepath in actual_watch_files:
                if Path(filepath).exists():
                    current_mtime = Path(filepath).stat().st_mtime
                    if filepath not in file_timestamps or current_mtime > file_timestamps[filepath]:
                        file_timestamps[filepath] = current_mtime
                        reload_needed = True
                        click.echo(f"ファイル変更を検出: {filepath}")
                        log_daemon_event("FILE_CHANGED", {"file": filepath})
            
            if reload_needed:
                click.echo("設定をリロードしています...")
                config = load_config()
                log_daemon_event("CONFIG_RELOAD", {})
            
            # リスナーを起動（バックグラウンド実行）
            try:
                asyncio.run(listen_main(
                    device=device,
                    all_devices=all_devices,
                    auto_route=auto_route,
                    debug=debug
                ))
            except Exception as e:
                click.echo(f"リスナーエラー: {e}", err=True)
                log_daemon_event("LISTENER_ERROR", {"error": str(e)})
                time.sleep(1)  # エラー時は少し待つ
            
            time.sleep(actual_reload_interval)
            
    except KeyboardInterrupt:
        click.echo("\nデーモンを停止しました。")
        log_daemon_event("DAEMON_STOP", {"reason": "keyboard_interrupt"})


def _run_once_mode(config, device, all_devices, auto_route, debug):
    """一回限りモード"""
    click.echo("一回限りのメッセージ待機を開始します...")
    
    try:
        asyncio.run(listen_main(
            device=device,
            all_devices=all_devices, 
            auto_route=auto_route,
            debug=debug
        ))
        click.echo("メッセージ処理が完了しました。")
    except KeyboardInterrupt:
        click.echo("\n待機を中止しました。")
    except Exception as e:
        click.echo(f"エラーが発生しました: {e}", err=True)


def _run_continuous_mode(config, device, all_devices, auto_route, debug):
    """継続的なメッセージ待機モード（シンプル）"""
    mode_desc = "自動ルーティング" if auto_route else (device or 'default')
    click.echo(f"メッセージ待機を開始します - モード: {mode_desc}")
    click.echo("Ctrl+Cで停止します...")
    
    try:
        asyncio.run(listen_main(
            device=device,
            all_devices=all_devices,
            auto_route=auto_route, 
            debug=debug
        ))
    except KeyboardInterrupt:
        click.echo("\nメッセージ待機を停止しました。")
    except Exception as e:
        click.echo(f"エラーが発生しました: {e}", err=True)