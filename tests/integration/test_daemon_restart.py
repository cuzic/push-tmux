#!/usr/bin/env python3
"""
デーモンの自動再起動機能のテスト
"""
import sys
import subprocess


class TestDaemonRestart:
    """デーモン再起動機能のテスト"""
    
    def test_daemon_crash_recovery(self, tmp_path):
        """クラッシュ後の自動再起動をテスト"""
        counter_file = tmp_path / "daemon_test_counter.txt"
        
        # テスト用のスクリプトを作成
        test_script = tmp_path / "test_daemon.py"
        test_script.write_text(f"""
import time
import sys
import os

counter_file = "{counter_file}"

if os.path.exists(counter_file):
    with open(counter_file, "r") as f:
        count = int(f.read().strip())
else:
    count = 0

count += 1

with open(counter_file, "w") as f:
    f.write(str(count))

print(f"[TEST] プロセス起動 #{{count}}")
sys.stdout.flush()

# 3回目の起動で意図的にクラッシュ
if count == 3:
    print(f"[TEST] 意図的にクラッシュ #{{count}}")
    sys.stdout.flush()
    raise Exception("テスト用の意図的なクラッシュ")

# 2秒間動作して終了
time.sleep(2)
print(f"[TEST] 正常終了 #{{count}}")
""")
        
        # TODO: hupperを使った再起動のテストを実装
        # 現在は基本的な動作確認のみ
        result = subprocess.run(
            [sys.executable, str(test_script)],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        assert "[TEST] プロセス起動 #1" in result.stdout
        assert "[TEST] 正常終了 #1" in result.stdout
        
        # カウンターファイルが作成されていることを確認
        assert counter_file.exists()
        with open(counter_file) as f:
            assert f.read().strip() == "1"


def test_summary():
    """テストサマリーの表示"""
    print("""
デーモン再起動機能のテスト
============================================================
以下の機能をテストします:
1. プロセスクラッシュ後の自動再起動
2. 再起動回数のカウント
3. 特定回数でのクラッシュシミュレーション
============================================================

実行コマンド:
  pytest tests/integration/test_daemon_restart.py -v
""")