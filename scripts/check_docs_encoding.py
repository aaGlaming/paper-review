# -*- coding: utf-8 -*-
"""docs 目录编码体检。

用法：
    python scripts/check_docs_encoding.py              # 检查 docs/ 下全部 .md
    python scripts/check_docs_encoding.py docs/plan    # 只查指定目录
    python scripts/check_docs_encoding.py --strict     # 有疑点即返回退出码 1

判定三类问题：
    1. 非法 UTF-8          —— 文件字节流解不开
    2. 替换符 U+FFFD       —— 写入时已经丢字节
    3. 双重编码乱码字      —— UTF-8 被按 GBK/GB18030 解码后再存回
    4. 连续 ASCII 问号     —— 中文被替换成 ?（不可逆）

前两类是硬错误；后两类按阈值报警，因为正文里偶尔会有正常的问号。
"""
import io
import os
import sys

MARKERS = ('锛', '銆', '鐨', '鏂', '浠', '鏄', '涓', '锟', '鍧', '璁', '鏃',
           '鏋', '鐘', '甯', '瑁', '佸', '喅', '闃', '闁', '劖', '娼', '灞',
           '鐎', '瑰', '閸', '閿', '閵', '閳', '閹', '鐠', '閺', '婵', '״')


def scan(path):
    raw = open(path, 'rb').read()
    problem = []
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as e:
        text = raw.decode('utf-8', errors='replace')
        problem.append(f'非法 UTF-8 @ 字节 {e.start}')

    fffd = text.count('\ufffd')
    if fffd:
        problem.append(f'替换符 {fffd} 处')

    marker = sum(text.count(m) for m in MARKERS)
    if marker:
        problem.append(f'双重编码乱码 {marker} 处')

    # 问号密集的行才可疑：中文被替换成 ? 时，一行里会连续出现多个。
    # 代码块内的 `field?`（TypeScript 可选属性）与 Markdown 的 `??` 不算。
    suspicious = []
    in_code = False
    for lineno, line in enumerate(text.split('\n'), 1):
        if line.lstrip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        q = line.count('?')
        if q >= 5 or '???' in line:
            suspicious.append((lineno, q, line[:60]))
    if suspicious:
        problem.append(f'问号密集行 {len(suspicious)} 行'
                       f'（首行 L{suspicious[0][0]}，含 {suspicious[0][1]} 个 ?）')

    return text, problem


def main(argv):
    strict = '--strict' in argv
    args = [a for a in argv[1:] if not a.startswith('--')]
    root = args[0] if args else 'docs'

    files = []
    if os.path.isfile(root):
        files = [root]
    else:
        for base, _, names in os.walk(root):
            for n in names:
                if n.lower().endswith(('.md', '.markdown')):
                    files.append(os.path.join(base, n))

    bad = 0
    for p in sorted(files):
        text, problems = scan(p)
        if problems:
            bad += 1
            print(f'[X] {p}')
            for x in problems:
                print(f'      {x}')
        else:
            print(f'[ok] {p}  ({len(text)} 字符)')

    print()
    print(f'合计 {len(files)} 个文件，有问题 {bad} 个')
    if bad:
        print('修复思路：git 里有干净版时优先 `git show HEAD:<path>` 取历史，'
              '只重写新增段落；不要对整份文件做 encode/decode 猜测。')
    return 1 if (bad and strict) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
