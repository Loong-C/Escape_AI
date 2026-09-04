# Escape AI

Escape AI 是面向 17 × 17 Escape 抽象策略游戏的计算研究平台。项目将依次建立经过交叉验证的规则引擎、精确求解器、基准 AI、AlphaZero 自对弈系统、模型联赛、研究棋谱库和本地棋谱查看器。

## 当前状态

- 正式规则：17 × 17；研究代码同时支持 3–17 的奇数棋盘。
- 规则来源：`F:\Personal\Code\Escape\docs\Rule.md`，冻结副本见 `docs/Rule.md`。
- 源代码与报告：`F:\Personal\Code\Escape_AI`。
- 大型产物：`G:\Escape\_AI`。
- 当前里程碑：双规则引擎、验证器、固定基线、OpenSpiel 与神经 PUCT 核心。

## 架构边界

- `src/escape_ai`：Python 参考实现、搜索、训练、评测和研究工具。
- `cpp`：C++20 优化规则核心与 Python 绑定。
- `viewer`：后续 React/Vite/Phaser 只读棋谱查看器。
- `configs`：可提交的实验配置；机器本地覆盖放在被忽略的 `configs/local.toml`。
- 大型数据不进入仓库。正式运行只在 Git 中保存配置、结果摘要和内容校验和。

## 环境

要求 Python 3.12、CMake 3.20+、MSVC 2022，以及支持 CUDA 的 PyTorch 环境。首次安装：

```powershell
pwsh scripts/bootstrap.ps1
```

运行质量检查与参考引擎随机验证：

```powershell
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy
.venv\Scripts\python -m pytest
.venv\Scripts\escape-ai validate --games 20 --sizes 3,5,9,17
.venv\Scripts\escape-ai differential --games 20 --sizes 3,5,9,17
.venv\Scripts\escape-ai validate-openspiel --games 20 --sizes 3,5,9,17
.venv\Scripts\escape-ai benchmark-baselines --games 4 --size 3
.venv\Scripts\escape-ai run-experiment --config configs/experiments/az-smoke-3x3.yaml
.venv\Scripts\escape-ai run-league --config configs/leagues/smoke-3x3-v1.yaml
.venv\Scripts\escape-ai run-lineage --config configs/lineages/smoke-3x3-v1.yaml
.venv\Scripts\escape-ai generate-research-games --config configs/games/research-smoke-3x3-v1.yaml
```

正式实验只接受已提交配置并要求干净工作树。Parquet replay、checkpoint 和带完整
Git/配置/数据/模型哈希的 manifest 会原子写入 `G:\Escape\_AI`。

`configs/lineages/lineage-{a,b,c}-17x17-v1.yaml` 定义了三条互相独立的
100,000 局正式谱系。每个 Parquet shard 都会更新恢复点；中断后只从已确认的
shard 边界继续，且配置或 Git commit 改变时拒绝混合续跑。

`bootstrap.ps1` 会安装首阶段依赖、建立 `G:\Escape\_AI` 目录并使用 MSVC 2022 构建 C++ 扩展。仅需重新编译时可运行 `pwsh scripts/build_cpp.ps1`。
