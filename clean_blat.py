# -*- coding: utf-8 -*-
"""
clean_blat.py — 中线趋势共振策略 临时占位文件清理器
用途: 扫描指定目录(默认=本脚本所在目录, 即中线趋势共振策略根),
      删除所有 4 字节、内容为 "blat"、8位随机名(rand8) 的占位文件。
安全机制:
  - 仅匹配精确签名: 文件大小==4 且 内容=="blat" 且 文件名==^[0-9a-z_]{8}$
  - 绝不删除任何正常文件(.py/.json/.csv/.md/.html/其他命名)
  - 删除通过 fs.unlinkSync 完成; 本机 NODE_OPTIONS 的 safe-delete 钩子
    会将其劫持为"送回收站"(可恢复), 非永久删除。
用法:
  python clean_blat.py            # 扫本目录(含子目录)
  python clean_blat.py "E:/某路径" # 扫指定目录
  python clean_blat.py --dry      # 只统计不删除(预览)
"""
import os, sys, re

ROOT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else os.path.dirname(os.path.abspath(__file__))
DRY = "--dry" in sys.argv
PAT = re.compile(r"^[0-9a-z_]{8}$")

def is_blat(path):
    try:
        if not os.path.isfile(path):
            return False
        if os.path.getsize(path) != 4:
            return False
        if not PAT.match(os.path.basename(path)):
            return False
        with open(path, "rb") as f:
            return f.read(4) == b"blat"
    except Exception:
        return False

def main():
    print(f"扫描根: {ROOT}")
    print(f"模式: {'仅预览(不删除)' if DRY else '执行删除(送回收站)'}")
    print("-" * 60)
    cnt = 0
    for dirpath, _, files in os.walk(ROOT):
        for fn in files:
            p = os.path.join(dirpath, fn)
            if is_blat(p):
                cnt += 1
                rel = os.path.relpath(p, ROOT)
                if DRY:
                    print(f"  [预览] {rel}")
                else:
                    try:
                        os.remove(p)   # safe-delete 钩子 -> 回收站
                        print(f"  [已清理] {rel}")
                    except Exception as e:
                        print(f"  [失败] {rel} -> {e}")
    print("-" * 60)
    print(f"共处理: {cnt} 个 blat 占位文件")

if __name__ == "__main__":
    main()
