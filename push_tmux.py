#!/usr/bin/env python3
"""
Pushbulletのメッセージをtmuxに送信するCLIツール（非同期版）
"""
import asyncio
import click
import os
import time
import toml
from dotenv import load_dotenv
from async_pushbullet import AsyncPushbullet, AsyncPushbulletListener
import questionary
import aiohttp

# .envファイルから環境変数を読み込む
load_dotenv()

# 設定ファイルのパスを定義
CONFIG_FILE = "config.toml"

def load_config():
    """
    設定ファイル (config.toml) を読み込む
    ファイルが存在しない場合は空の辞書を返す
    """
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return toml.load(f)
    return {}

def save_config(config):
    """
    設定をTOML形式で設定ファイルに書き込む
    """
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        toml.dump(config, f)

def get_device_name():
    """
    環境変数またはディレクトリ名からデバイス名を取得する
    """
    return os.getenv('DEVICE_NAME', os.path.basename(os.getcwd()))

async def send_to_tmux(config, message, device_name=None):
    """
    tmuxにメッセージとEnterキーを送信する
    
    Args:
        config: 設定辞書
        message: 送信するメッセージ
        device_name: デバイス名（tmuxセッション名として使用）
    """
    tmux_config = config.get('tmux', {})
    session_setting = tmux_config.get('target_session')
    window_setting = tmux_config.get('target_window')
    pane_setting = tmux_config.get('target_pane')
    
    # ターゲットセッションを決定
    target_session = None
    
    # 優先順位: 1. config設定 2. device_name 3. 現在のセッション
    # configに明示的な設定がある場合はそれを優先
    if session_setting and session_setting != 'current':
        target_session = session_setting
    
    # config設定がない場合、device_nameを使用
    elif device_name:
        # デバイス名と同じ名前のtmuxセッションが存在するか確認
        try:
            result = await asyncio.create_subprocess_exec(
                'tmux', 'has-session', '-t', device_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            if result.returncode == 0:
                target_session = device_name
                click.echo(f"デバイス名に対応するtmuxセッション '{device_name}' を使用します。")
            else:
                click.echo(f"警告: tmuxセッション '{device_name}' が存在しません。フォールバックします。")
        except:
            pass
    
    # configもdevice_nameもない、またはdevice_nameでセッションが見つからなかった場合
    if target_session is None:
        # TMUX環境変数から現在のセッション情報を取得
        tmux_env = os.environ.get('TMUX')
        if tmux_env:
            # tmux display-messageで現在のセッション名を取得
            try:
                result = await asyncio.create_subprocess_exec(
                    'tmux', 'display-message', '-p', '#{session_name}',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await result.communicate()
                target_session = stdout.decode().strip()
            except:
                # フォールバック
                parts = tmux_env.split(',')
                if parts:
                    socket_path = parts[0]
                    session_name = os.path.basename(socket_path)
                    target_session = session_name if session_name else 'default'
        else:
            click.echo("エラー: スクリプトがtmuxセッション内で実行されていません。", err=True)
            click.echo("`config.toml`で`[tmux].target_session`を明示的に設定してください。", err=True)
            return
    
    # デフォルト値の設定
    # ウィンドウ: 設定がない場合は実際の最初のウィンドウを取得
    if window_setting is None or window_setting == 'first':
        try:
            result = await asyncio.create_subprocess_exec(
                'tmux', 'list-windows', '-t', target_session, '-F', '#{window_index}',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            windows = stdout.decode().strip().split('\n')
            target_window = windows[0] if windows else '0'
        except:
            target_window = '0'
    else:
        target_window = window_setting
    
    # ペイン: 設定がない場合は実際の最初のペインを取得
    if pane_setting is None or pane_setting == 'first':
        try:
            result = await asyncio.create_subprocess_exec(
                'tmux', 'list-panes', '-t', f"{target_session}:{target_window}", '-F', '#{pane_index}',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            panes = stdout.decode().strip().split('\n')
            target_pane = panes[0] if panes else '0'
        except:
            target_pane = '0'
    else:
        target_pane = pane_setting
    
    target = f"{target_session}:{target_window}.{target_pane}"
    
    try:
        # メッセージを送信
        click.echo(f"tmuxセッション '{target}' にメッセージを送信します...")
        process = await asyncio.create_subprocess_exec(
            'tmux', 'send-keys', '-t', target, message
        )
        await process.wait()
        
        # 1秒待機
        await asyncio.sleep(1)
        
        # Enterキーを送信
        click.echo("Enterキーを送信します...")
        process = await asyncio.create_subprocess_exec(
            'tmux', 'send-keys', '-t', target, 'C-m'
        )
        await process.wait()
        click.echo("tmuxへの送信が完了しました。")
        
    except FileNotFoundError:
        click.echo("エラー: 'tmux'コマンドが見つかりません。パスが通っているか確認してください。", err=True)
    except Exception as e:
        click.echo(f"tmuxコマンドの実行中にエラーが発生しました: {e}", err=True)


# --- CLIコマンド定義 ---

@click.group()
def cli():
    """
    Pushbulletのメッセージをtmuxに送信するCLIツール。
    """
    pass

@cli.command()
@click.option('--name', help='デバイス名（未指定時は環境変数DEVICE_NAME）')
def register(name):
    """
    新しいPushbulletデバイスとして登録します。
    """
    async def _register():
        api_key = os.getenv('PUSHBULLET_TOKEN')
        if not api_key:
            click.echo("エラー: PUSHBULLET_TOKEN環境変数が設定されていません。", err=True)
            return
        
        device_name = name if name else get_device_name()
        
        async with AsyncPushbullet(api_key) as pb:
            try:
                devices = await pb.get_devices()
                existing_device = next((d for d in devices if d.get('nickname') == device_name), None)
                
                if existing_device:
                    click.echo(f"デバイス '{device_name}' は既に登録されています。")
                    click.echo(f"  ID: {existing_device['iden']}")
                    click.echo(f"  作成日時: {existing_device['created']}")
                    click.echo(f"  更新日時: {existing_device['modified']}")
                else:
                    device = await pb.create_device(device_name)
                    click.echo(f"デバイス '{device_name}' を登録しました。")
                    click.echo(f"  ID: {device['iden']}")
            except Exception as e:
                click.echo(f"デバイス登録中にエラーが発生しました: {e}", err=True)
    
    asyncio.run(_register())

@cli.command('list-devices')
def list_devices():
    """
    Pushbulletに登録されているデバイス一覧を表示します。
    """
    async def _list_devices():
        api_key = os.getenv('PUSHBULLET_TOKEN')
        if not api_key:
            click.echo("エラー: PUSHBULLET_TOKEN環境変数が設定されていません。", err=True)
            return
        
        async with AsyncPushbullet(api_key) as pb:
            try:
                devices = await pb.get_devices()
                if not devices:
                    click.echo("登録されているデバイスはありません。")
                    return
                
                click.echo("\n登録されているデバイス一覧:")
                click.echo("=" * 60)
                for device in devices:
                    click.echo(f"\n名前: {device.get('nickname', 'N/A')}")
                    click.echo(f"  ID: {device['iden']}")
                    click.echo(f"  アクティブ: {'はい' if device.get('active', False) else 'いいえ'}")
                    click.echo(f"  作成日時: {device.get('created', 'N/A')}")
                    click.echo(f"  更新日時: {device.get('modified', 'N/A')}")
                    if 'manufacturer' in device:
                        click.echo(f"  製造元: {device['manufacturer']}")
                    if 'model' in device:
                        click.echo(f"  モデル: {device['model']}")
                click.echo("\n" + "=" * 60)
                click.echo(f"合計: {len(devices)} デバイス")
            except Exception as e:
                click.echo(f"デバイス一覧の取得中にエラーが発生しました: {e}", err=True)
    
    asyncio.run(_list_devices())

@cli.command('delete-devices')
@click.option('--name', help='削除するデバイス名（単一削除モード）')
@click.option('--id', 'device_id', help='削除するデバイスID（単一削除モード）')
@click.option('--yes', is_flag=True, help='確認なしで削除（単一削除モード）')
@click.option('--include-inactive', is_flag=True, help='非アクティブなデバイスも表示（複数選択モード）')
def delete_devices(name, device_id, yes, include_inactive):
    """
    Pushbulletデバイスを削除します。
    
    引数なし: インタラクティブに複数デバイスを選択して削除
    --name/--id指定: 特定のデバイスを直接削除
    """
    async def _delete_devices():
        api_key = os.getenv('PUSHBULLET_TOKEN')
        if not api_key:
            click.echo("エラー: PUSHBULLET_TOKEN環境変数が設定されていません。", err=True)
            return
        
        # 単一削除モード（--nameまたは--id指定時）
        if name or device_id:
            async with AsyncPushbullet(api_key) as pb:
                try:
                    devices = await pb.get_devices()
                    target_device = None
                    
                    for device in devices:
                        if device_id and device['iden'] == device_id:
                            target_device = device
                            break
                        elif name and device.get('nickname') == name:
                            target_device = device
                            break
                    
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
                    
                    await pb.delete_device(target_device['iden'])
                    click.echo(f"デバイス '{target_device.get('nickname', 'N/A')}' (ID: {target_device['iden']}) を削除しました。")
                    
                except Exception as e:
                    click.echo(f"デバイス削除中にエラーが発生しました: {e}", err=True)
                return
        
        # 複数選択削除モード
        async with AsyncPushbullet(api_key) as pb:
            try:
                # デバイス一覧を取得（デフォルトはアクティブのみ）
                devices = await pb.get_devices(active_only=not include_inactive)
                if not devices:
                    if include_inactive:
                        click.echo("登録されているデバイスはありません。")
                    else:
                        click.echo("アクティブなデバイスはありません。")
                        click.echo("非アクティブなデバイスも表示するには --include-inactive オプションを使用してください。")
                    return
                
                # デバイスの選択肢を作成
                choices = []
                for device in devices:
                    name = device.get('nickname', 'N/A')
                    iden = device['iden']
                    active = "✓" if device.get('active', False) else " "
                    created = device.get('created', 'N/A')
                    
                    # 作成日時をフォーマット
                    if created != 'N/A':
                        from datetime import datetime
                        try:
                            dt = datetime.fromtimestamp(created)
                            created_str = dt.strftime('%Y-%m-%d %H:%M')
                        except:
                            created_str = str(created)
                    else:
                        created_str = 'N/A'
                    
                    # 製造元とモデル情報
                    manufacturer = device.get('manufacturer', '')
                    model = device.get('model', '')
                    device_info = f" ({manufacturer} {model})" if manufacturer or model else ""
                    
                    label = f"[{active}] {name:<20} (ID: {iden[:10]}...) 作成: {created_str}{device_info}"
                    choices.append(questionary.Choice(title=label, value=device))
                
                # チェックボックスで複数選択
                selected_devices = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: questionary.checkbox(
                        "削除するデバイスを選択してください (スペースで選択/解除, Enterで確定):",
                        choices=choices
                    ).ask()
                )
                
                if not selected_devices:
                    click.echo("削除をキャンセルしました。")
                    return
                
                # 選択されたデバイスの詳細を表示
                click.echo("\n以下のデバイスを削除します:")
                click.echo("=" * 60)
                for device in selected_devices:
                    click.echo(f"  • {device.get('nickname', 'N/A')} (ID: {device['iden']})")
                click.echo("=" * 60)
                
                # 最終確認
                confirm = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: questionary.confirm(
                        f"\n{len(selected_devices)}個のデバイスを削除してもよろしいですか？"
                    ).ask()
                )
                
                if not confirm:
                    click.echo("削除をキャンセルしました。")
                    return
                
                # デバイスを一括削除
                click.echo("\nデバイスを削除中...")
                success_count = 0
                error_count = 0
                
                for device in selected_devices:
                    try:
                        await pb.delete_device(device['iden'])
                        click.echo(f"  ✓ {device.get('nickname', 'N/A')} (ID: {device['iden']}) を削除しました")
                        success_count += 1
                    except aiohttp.ClientResponseError as e:
                        if e.status == 404:
                            # 既に削除されているデバイス
                            click.echo(f"  ⚠ {device.get('nickname', 'N/A')} (ID: {device['iden']}) は既に削除されています")
                        else:
                            click.echo(f"  ✗ {device.get('nickname', 'N/A')} (ID: {device['iden']}) の削除に失敗: {e}", err=True)
                            error_count += 1
                    except Exception as e:
                        click.echo(f"  ✗ {device.get('nickname', 'N/A')} (ID: {device['iden']}) の削除に失敗: {e}", err=True)
                        error_count += 1
                
                # 結果のサマリーを表示
                click.echo("\n" + "=" * 60)
                click.echo(f"削除完了: {success_count}個のデバイス")
                if error_count > 0:
                    click.echo(f"削除失敗: {error_count}個のデバイス", err=True)
                
            except Exception as e:
                click.echo(f"デバイス一覧の取得中にエラーが発生しました: {e}", err=True)
    
    asyncio.run(_delete_devices())

@cli.command('send-key')
@click.argument('message')
@click.option('--session', help='ターゲットセッション')
@click.option('--window', help='ターゲットウィンドウ')
@click.option('--pane', help='ターゲットペイン')
def send_key(message, session, window, pane):
    """
    tmuxにメッセージを送信します（テスト用）。
    """
    async def _send_key():
        config = load_config()
        
        if session or window or pane:
            if 'tmux' not in config:
                config['tmux'] = {}
            if session:
                config['tmux']['target_session'] = session
            if window:
                config['tmux']['target_window'] = window
            if pane:
                config['tmux']['target_pane'] = pane
        
        await send_to_tmux(config, message, device_name=None)
    
    asyncio.run(_send_key())

@cli.command()
@click.option('--device', help='メッセージを受信するデバイス名またはID')
@click.option('--all-devices', is_flag=True, help='全デバイス宛のメッセージを受信')
@click.option('--auto-route', is_flag=True, help='デバイス名と同じtmuxセッションに自動ルーティング')
@click.option('--debug', is_flag=True, help='デバッグモードで実行（詳細ログを表示）')
def listen(device, all_devices, auto_route, debug):
    """
    Pushbulletからのメッセージを待ち受け、tmuxに送信します。
    """
    async def _listen():
        api_key = os.getenv('PUSHBULLET_TOKEN')
        if not api_key:
            click.echo("エラー: PUSHBULLET_TOKEN環境変数が設定されていません。", err=True)
            return
        
        config = load_config()
        
        # auto-routeモードの場合、全デバイスのメッセージを受信
        if auto_route:
            click.echo("自動ルーティングモード: 全デバイスのメッセージを受信し、対応するtmuxセッションに送信します。")
            
            # デバイス一覧を取得して表示
            async with AsyncPushbullet(api_key) as pb:
                try:
                    devices = await pb.get_devices(active_only=True)
                    if devices:
                        click.echo("\nアクティブなデバイス:")
                        for d in devices:
                            nickname = d.get('nickname', 'N/A')
                            # tmuxセッションの存在確認
                            try:
                                result = await asyncio.create_subprocess_exec(
                                    'tmux', 'has-session', '-t', nickname,
                                    stdout=asyncio.subprocess.PIPE,
                                    stderr=asyncio.subprocess.PIPE
                                )
                                await result.communicate()
                                session_exists = result.returncode == 0
                                status = "✓ tmuxセッションあり" if session_exists else "✗ tmuxセッションなし"
                            except:
                                status = "? tmux確認失敗"
                            
                            click.echo(f"  - {nickname} ({d['iden'][:8]}...) [{status}]")
                        click.echo("")
                except Exception as e:
                    click.echo(f"デバイス一覧取得エラー: {e}")
        
        # ターゲットデバイスの特定
        target_device_iden = None
        device_name = None  # デバイス名を保持
        if device and not all_devices and not auto_route:
            async with AsyncPushbullet(api_key) as pb:
                try:
                    devices = await pb.get_devices()
                    for d in devices:
                        if d.get('nickname') == device or d.get('iden') == device:
                            target_device_iden = d['iden']
                            device_name = d.get('nickname', d['iden'])
                            click.echo(f"デバイス '{device_name}' (ID: {d['iden']}) として待ち受けます。")
                            break
                    
                    if not target_device_iden:
                        click.echo(f"エラー: デバイス '{device}' が見つかりません。", err=True)
                        return
                except Exception as e:
                    click.echo(f"デバイス情報の取得中にエラーが発生しました: {e}", err=True)
                    return
        elif all_devices and not auto_route:
            click.echo("警告: --all-devicesオプションは無効です。特定のデバイス宛のメッセージのみ処理します。")
        elif not auto_route:
            # デフォルト：現在のデバイス名で登録されているデバイスを使用
            device_name = get_device_name()
            async with AsyncPushbullet(api_key) as pb:
                try:
                    devices = await pb.get_devices()
                    for d in devices:
                        if d.get('nickname') == device_name:
                            target_device_iden = d['iden']
                            click.echo(f"デバイス '{device_name}' (ID: {d['iden']}) として待ち受けます。")
                            break
                    
                    if not target_device_iden:
                        click.echo(f"エラー: デバイス '{device_name}' が登録されていません。", err=True)
                        click.echo("先に 'push-tmux register' でデバイスを登録してください。", err=True)
                        return
                except Exception as e:
                    click.echo(f"デバイス情報を取得できませんでした: {e}", err=True)
                    return
        
        # auto-routeモード用のハンドラー
        if auto_route:
            # デバイス情報をキャッシュ
            device_cache = {}
            async with AsyncPushbullet(api_key) as pb:
                devices = await pb.get_devices()
                for d in devices:
                    device_cache[d['iden']] = d.get('nickname', d['iden'])
            
            async def on_push_auto_route(push):
                """自動ルーティングモードでのプッシュ処理"""
                # noteタイプのみ処理
                if push.get('type') != 'note':
                    return
                
                # デバイス情報を取得
                target_device_iden = push.get('target_device_iden')
                
                # 全デバイス宛のメッセージは無視
                if not target_device_iden:
                    return
                
                # デバイス名を取得
                target_device_name = device_cache.get(target_device_iden, None)
                if not target_device_name:
                    click.echo(f"警告: 未知のデバイスID: {target_device_iden}")
                    return
                
                # tmuxセッションの存在確認
                try:
                    result = await asyncio.create_subprocess_exec(
                        'tmux', 'has-session', '-t', target_device_name,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await result.communicate()
                    session_exists = result.returncode == 0
                except:
                    session_exists = False
                
                if not session_exists:
                    # セッションが存在しない場合はスキップ（ログのみ）
                    click.echo(f"[スキップ] {target_device_name}: tmuxセッションが存在しません")
                    return
                
                # メッセージ情報を表示
                title = push.get('title', 'メッセージ')
                body = push.get('body', '')
                sender_name = push.get('sender_name', '不明')
                
                click.echo("-" * 40)
                click.echo(f"メッセージを {target_device_name} セッションに送信:")
                click.echo(f"  送信者: {sender_name}")
                click.echo(f"  タイトル: {title}")
                click.echo(f"  本文: {body[:50]}..." if len(body) > 50 else f"  本文: {body}")
                click.echo("-" * 40)
                
                # tmuxに送信（デバイス名を指定）
                await send_to_tmux(config, body, device_name=target_device_name)
            
            on_push = on_push_auto_route
        else:
            # 既存のon_push関数（特定デバイスモード）
            async def on_push(push):
                """プッシュを受信したときの処理"""
                # noteタイプのみ処理
                if push.get('type') != 'note':
                    return
                
                # デバイスフィルタリング
                target_device = push.get('target_device_iden')
                
                # 全デバイス宛のメッセージは無視
                if not target_device:
                    return
                
                # 特定のデバイス宛のメッセージのみ処理
                # target_device_idenが設定されている場合は、そのデバイス宛のメッセージのみ処理
                if target_device != target_device_iden:
                    # 他のデバイス宛のメッセージは無視
                    return
                
                title = push.get('title', 'メッセージ')
                body = push.get('body', '')
                sender_name = push.get('sender_name', '不明')
                sender_email = push.get('sender_email', '')
                
                click.echo("-" * 40)
                click.echo(f"新しいメッセージを受信しました:")
                if sender_email:
                    click.echo(f"  送信者: {sender_name} ({sender_email})")
                else:
                    click.echo(f"  送信者: {sender_name}")
                click.echo(f"  宛先デバイス: {target_device}")
                click.echo(f"  タイトル: {title}")
                click.echo(f"  本文: {body}")
                click.echo("-" * 40)
                
                # tmuxに送信 (デバイス名を渡す)
                # 外側のスコープのdevice_nameを参照
                await send_to_tmux(config, body, device_name=device_name)
        
        # リスナーを開始（デバッグモード対応）
        listener = AsyncPushbulletListener(api_key, on_push, debug=debug)
        
        if debug:
            click.echo("デバッグモードで実行中...")
        click.echo(f"Pushbulletのストリームを開始します。")
        click.echo("Ctrl+Cで終了します。")
        
        try:
            await listener.run()
        except KeyboardInterrupt:
            click.echo("\nストリームを停止します...")
        except Exception as e:
            click.echo(f"Pushbulletのストリームでエラーが発生しました: {e}", err=True)
        finally:
            click.echo("Pushbulletのストリームを終了しました。")
    
    asyncio.run(_listen())

if __name__ == "__main__":
    cli()