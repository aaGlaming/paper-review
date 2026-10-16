// 「不许出现」的词表：source-scan.spec.ts 与 parse-view.spec.ts 共用这一处定义。
//
// 本文件是唯一允许出现这些字面量的地方——词表没法扫描自己。
// 扫描时按文件名排除本文件与 source-scan.spec.ts，其余 src/ 与 tests/ 下的文件一律扫。

export const AWARD_WORDS = ['一等奖', '二等奖', '三等奖', '获奖概率', '获奖', '名次']

export const CONTEST_ID_TOKEN = 'cumcm-'

export const WORDLIST_FILES = new Set(['forbidden-words.ts', 'source-scan.spec.ts'])
