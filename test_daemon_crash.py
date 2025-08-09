#!/usr/bin/env python3
"""
Daemon の自動再起動テスト用スクリプト
"""
import time
import sys
import os

# カウンターファイルで再起動回数を記録
counter_file = "/tmp/daemon_test_counter.txt"

if os.path.exists(counter_file):
    with open(counter_file, "r") as f:
        count = int(f.read().strip())
else:
    count = 0

count += 1

with open(counter_file, "w") as f:
    f.write(str(count))

print(f"[TEST] プロセス起動 #{count}")
sys.stdout.flush()

# 3回目の起動で意図的にクラッシュ
if count == 3:
    print(f"[TEST] 意図的にクラッシュ #{count}")
    sys.stdout.flush()
    raise Exception("テスト用の意図的なクラッシュ")

# 5秒間動作して終了
time.sleep(5)
print(f"[TEST] 正常終了 #{count}")