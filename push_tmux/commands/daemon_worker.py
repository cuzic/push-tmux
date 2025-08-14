#!/usr/bin/env python3
"""
Daemon worker process for push-tmux
"""

import asyncio
import os
from ..logging import log_daemon_event
from .listen import listen_main


def main():
    """デーモンワーカーのメイン処理"""
    try:
        # 環境変数から設定を復元
        device = os.getenv("PUSH_TMUX_DEVICE") or None
        if device == "":
            device = None
        all_devices = os.getenv("PUSH_TMUX_ALL_DEVICES") == "1"
        auto_route = os.getenv("PUSH_TMUX_AUTO_ROUTE") == "1"
        debug = os.getenv("PUSH_TMUX_DEBUG") == "1"

        log_daemon_event(
            "info",
            "ワーカーを開始",
            device=device or "default",
            all_devices=all_devices,
            auto_route=auto_route,
            debug=debug,
        )

        # listen_mainを実行（asyncio.runでラップ）
        asyncio.run(listen_main(device, all_devices, auto_route, debug))

    except KeyboardInterrupt:
        log_daemon_event("info", "ワーカーを停止")
    except Exception as e:
        log_daemon_event("error", f"ワーカーでエラー: {e}")
        raise


if __name__ == "__main__":
    main()
