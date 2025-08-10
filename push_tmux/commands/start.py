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
    if not _validate_start_options(daemon, once):
        return
    
    processed_args = _process_start_arguments(device, all_devices, auto_route, no_auto_route)
    config = load_config()
    
    _execute_start_mode(config, processed_args, daemon, once, debug, reload_interval, watch_files)


def _validate_start_options(daemon, once):
    """引数の検証"""
    if daemon and once:
        click.echo("エラー: --daemon と --once は同時に指定できません。", err=True)
        return False
    return True


def _process_start_arguments(device, all_devices, auto_route, no_auto_route):
    """引数を処理して正規化する"""
    # 引数がない場合は自動ルーティングをデフォルトに
    if not device and not all_devices and not auto_route and not no_auto_route:
        auto_route = True
        
    # no_auto_route が指定された場合は auto_route を無効化
    if no_auto_route:
        auto_route = False
    
    return {
        'device': device,
        'all_devices': all_devices,
        'auto_route': auto_route
    }


def _execute_start_mode(config, processed_args, daemon, once, debug, reload_interval, watch_files):
    """適切なモードでstart処理を実行"""
    if daemon:
        # デーモンモード - ファイル監視とホットリロード機能
        _run_daemon_mode(config, processed_args['device'], processed_args['all_devices'], 
                        processed_args['auto_route'], debug, reload_interval, watch_files)
    elif once:
        # 一回限りモード - 単発のメッセージ待機
        _run_once_mode(config, processed_args['device'], processed_args['all_devices'], 
                      processed_args['auto_route'], debug)
    else:
        # デフォルト - 継続的なメッセージ待機（シンプル）
        _run_continuous_mode(config, processed_args['device'], processed_args['all_devices'], 
                           processed_args['auto_route'], debug)


def _run_daemon_mode(config, device, all_devices, auto_route, debug, reload_interval, watch_files):
    """デーモンモード - ファイル変更監視付き"""
    setup_logging(config, is_daemon=True)
    
    daemon_settings = _prepare_daemon_settings(config, reload_interval, watch_files)
    mode_desc = "自動ルーティング" if auto_route else (device or 'default')
    
    _log_daemon_start(mode_desc, daemon_settings)
    file_timestamps = _initialize_file_timestamps(daemon_settings['watch_files'])
    _setup_daemon_signal_handlers()
    
    _run_daemon_main_loop(file_timestamps, daemon_settings, device, all_devices, auto_route, debug)


def _prepare_daemon_settings(config, reload_interval, watch_files):
    """デーモンの設定を準備する"""
    daemon_config = config.get('daemon', {})
    default_watch_files = daemon_config.get('watch_files', ['config.toml', '.env'])
    actual_watch_files = list(watch_files) if watch_files else default_watch_files
    actual_reload_interval = reload_interval if reload_interval != 1.0 else daemon_config.get('reload_interval', 1.0)
    
    return {
        'watch_files': actual_watch_files,
        'reload_interval': actual_reload_interval
    }


def _log_daemon_start(mode_desc, daemon_settings):
    """デーモン開始のログを出力"""
    click.echo(f"デーモンモード開始 - モード: {mode_desc}")
    click.echo(f"監視ファイル: {daemon_settings['watch_files']}")
    click.echo(f"監視間隔: {daemon_settings['reload_interval']}秒")
    
    log_daemon_event("DAEMON_START", {
        "mode": mode_desc,
        "watch_files": daemon_settings['watch_files'],
        "reload_interval": daemon_settings['reload_interval']
    })


def _initialize_file_timestamps(watch_files):
    """ファイルのタイムスタンプを初期化"""
    file_timestamps = {}
    for filepath in watch_files:
        if Path(filepath).exists():
            file_timestamps[filepath] = Path(filepath).stat().st_mtime
    return file_timestamps


def _setup_daemon_signal_handlers():
    """デーモン用のシグナルハンドラーを設定"""
    def signal_handler(signum, frame):
        click.echo("\nデーモンを停止しています...")
        log_daemon_event("DAEMON_STOP", {"signal": signum})
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def _run_daemon_main_loop(file_timestamps, daemon_settings, device, all_devices, auto_route, debug):
    """デーモンのメインループを実行"""
    try:
        while True:
            reload_needed = _check_file_changes(file_timestamps, daemon_settings['watch_files'])
            
            if reload_needed:
                _handle_config_reload()
            
            _run_listener_iteration(device, all_devices, auto_route, debug)
            time.sleep(daemon_settings['reload_interval'])
            
    except KeyboardInterrupt:
        click.echo("\nデーモンを停止しました。")
        log_daemon_event("DAEMON_STOP", {"reason": "keyboard_interrupt"})


def _check_file_changes(file_timestamps, watch_files):
    """ファイルの変更をチェック"""
    reload_needed = False
    for filepath in watch_files:
        if Path(filepath).exists():
            current_mtime = Path(filepath).stat().st_mtime
            if filepath not in file_timestamps or current_mtime > file_timestamps[filepath]:
                file_timestamps[filepath] = current_mtime
                reload_needed = True
                click.echo(f"ファイル変更を検出: {filepath}")
                log_daemon_event("FILE_CHANGED", {"file": filepath})
    return reload_needed


def _handle_config_reload():
    """設定のリロードを処理"""
    click.echo("設定をリロードしています...")
    config = load_config()
    log_daemon_event("CONFIG_RELOAD", {})
    return config


def _run_listener_iteration(device, all_devices, auto_route, debug):
    """リスナーの1回の実行を処理"""
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