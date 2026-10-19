# WordleSolver

基于信息熵的 Wordle 自动求解 / 辅助猜词工具。优先最小化**平均步数**，支持 Hard Mode。

## 功能

- **交互辅助** (`play`)：根据颜色反馈推荐下一步猜测
- **自动求解** (`auto`)：对指定答案走出完整猜词路径
- **批量模拟** (`simulate`)：在全部答案词上统计胜率与平均步数
- **Hard Mode**：后续猜测必须使用已揭示的绿/黄线索

## 快速开始

需要 Python 3.10+。无第三方依赖。

```bash
# 交互辅助（普通模式）
python main.py play

# Hard Mode 辅助
python main.py play --hard

# 自动求解某个词
python main.py auto crane

# 抽样模拟（先跑 50 个验证）
python main.py simulate --limit 50

# 全量模拟（约数分钟）
python main.py simulate

# Hard Mode 全量模拟
python main.py simulate --hard

# 预计算最佳开局（--fast 只用答案池，更快）
python main.py opener --fast
```

## 交互反馈格式

用 `g` / `y` / `b` 表示绿 / 黄 / 灰，例如：

```
slate gybbb
```

也支持分两行输入猜测与反馈。

## 算法说明

每一步对猜测池中的词计算：若该猜测作为下一猜，会把当前候选集划分成哪些反馈桶，再取香农熵最大的词。平局时优先选仍在答案候选集中的词（本回合有机会直接猜中）。

开局词会缓存到 `words/opener_cache.json`，避免重复全表扫描。

## 词表

- `words/answers.txt` — 可能的答案（~2309）
- `words/guesses.txt` — 合法猜测（含答案，~14855）

来源：[Roy-Orbison/wordle-guesses-answers](https://github.com/Roy-Orbison/wordle-guesses-answers)
