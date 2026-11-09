# 基于图像与视频的停车场收费系统

这是一个面向软件工程课程实践的 Windows 单机桌面程序。系统使用 Python、PyQt5、SQLite、OpenCV 与 HyperLPR3，演示从车辆进场到出场结算的完整业务闭环：

```text
图片/视频输入 → 车牌识别 → 进场登记 → 出场计费
→ 模拟缴费 → 道闸动画 → 离场确认 → 记录查询
```

项目优先保证可运行、可演示和可验证，不连接真实道闸或支付平台。

## 当前进度

| 阶段 | 状态 | 已实现内容 |
| --- | --- | --- |
| Phase 1 | 已完成 | SQLite 数据持久化、计费算法、收费规则管理、登录与权限 |
| Phase 2 | 已完成 | 手工录入进出场、模拟缴费、放行控制、主界面与 3D 道闸动画联调 |
| Phase 3 | 核心功能已完成 | 真实图片/视频车牌识别、后台线程、候选选择、失败后人工补录、抓拍路径入库 |
| Phase 4 | 已验收 | 天/ISO 周/月/季/年统计、中文 PDF 报表、可重复独立演示数据 |
| Phase 5 | 进行中 | 真实媒体、TC-01～TC-12、性能容量、部署与答辩交付 |

Phase 3 当前支持：

- 图片格式：JPG、JPEG、PNG、BMP。
- 视频格式：MP4、AVI、MOV、MKV。
- 识别任务在 `QThread` 中运行，避免长期阻塞界面。
- 默认置信度阈值为 `0.80`，最多执行 3 次图片增强或视频抽帧识别。
- 多候选或结果存在歧义时，由操作员选择；识别失败时可切换到人工录入。
- 识别结果继续复用 Phase 2 的进场、计费、缴费和放行业务状态，不绕过业务校验。

## 目录结构

```text
RJKF/
├─ Module A/parking_system/
│  ├─ app.py                       # 程序入口
│  ├─ parking/
│  │  ├─ recognition/              # 图片/视频车牌识别
│  │  ├─ services/                 # 停车、规则与管理业务
│  │  ├─ data/                     # SQLite 数据访问
│  │  ├─ anim/                     # 道闸动画适配
│  │  └─ ui/                       # PyQt5 界面
│  ├─ tests/                       # pytest 自动化测试
│  ├─ tools/                       # 模型准备与自检脚本
│  └─ runtime/                     # 本地数据库、模型和抓拍文件（不提交 Git）
├─ Docs/                           # 需求与设计文档
├─ PLANT.md                        # 分阶段开发计划和验证记录
└─ git.md                          # 项目 Git 工作流
```

## 运行环境

- Windows 10/11
- Python 3.12（当前开发验证版本为 3.12.8）
- 建议使用项目根目录下的独立虚拟环境 `.venv`

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r "Module A\parking_system\requirements.txt"
```

如需运行自动化测试，再安装开发依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r "Module A\parking_system\requirements-dev.txt"
```

## 准备识别模型

首次使用车牌识别前执行：

```powershell
.\.venv\Scripts\python.exe "Module A\parking_system\tools\setup_recognition.py"
```

脚本会把 HyperLPR3 模型准备到 `Module A/parking_system/runtime/.hyperlpr3`。依赖和模型准备完成后，应用可离线执行识别。`runtime` 目录已被 Git 忽略，不会把模型、数据库或抓拍图片提交到仓库。

## 运行 Phase 5 图片识别基准

准备带真值的图片清单后，在仓库根目录执行：

```powershell
Push-Location "Module A\parking_system"
& "..\..\.venv\Scripts\python.exe" "tools\phase5_recognition_benchmark.py"
Pop-Location
```

工具使用与 GUI 相同的 HyperLPR3 模型、`0.80` 阈值和最多 3 次识别尝试，按整牌完全一致计算自动识别准确率，并记录模型预加载、100 张批处理、逐图耗时、失败原因和软硬件环境。逐张 CSV 与汇总 JSON 写入已忽略的 `runtime/phase5/recognition/`，不会修改业务数据库。默认真值清单为仓库根目录下的 `res/phase5_images/final/ground_truth.csv`，也可通过 `--manifest` 指定其他清单。

2026-11-06 的首轮混合集结果为 77/100，100 张批处理 55.722 秒；性能目标通过，准确率目标未通过。该集合包含 `ccpd_fn` 远近距离样本、模糊/倾斜画面和双层黄牌，保留用于鲁棒性回归，不能替代仍待冻结的“车牌完整、光照正常”准确率验收集。

## 启动程序

```powershell
.\.venv\Scripts\python.exe "Module A\parking_system\app.py"
```

首次运行且数据库中没有账号时，登录窗口会引导创建管理员账号。

典型操作流程：

1. 进场：选择图片或视频，确认识别结果；失败时可人工录入，然后登记进场并抬杆。
2. 出场：选择图片或视频或人工输入车牌，查询在场记录并计算费用。
3. 缴费：完成模拟缴费后才能放行；未缴费车辆不会被直接标记为离场。
4. 离场：抬杆、确认车辆通过、落杆，随后可在记录查询中核对数据。
5. 报表：管理员打开“统计报表”，选择包含起点、不包含终点的日期区间和统计维度，可查询并导出、打开或打印 PDF。

## 生成独立演示数据

在仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe "Module A\parking_system\tools\generate_demo_data.py"
```

默认生成 `Module A/parking_system/runtime/demo/parking.sqlite3`，使用固定随机种子，包含 240 个车牌、1000 条已离场记录、五类计费场景各 200 条及 20 条以上异常车牌输入。重复运行会替换本工具管理的演示库而不会叠加；脚本始终拒绝覆盖实际业务数据库。演示登录账号为 `demo_admin`，密码为 `DemoPass123`，仅用于这个独立演示库。

使用演示库启动时，在同一个 PowerShell 窗口执行：

```powershell
$env:PARKING_DATA_DIR = (Resolve-Path "Module A\parking_system\runtime\demo").Path
.\.venv\Scripts\python.exe "Module A\parking_system\tools\setup_recognition.py"
.\.venv\Scripts\python.exe "Module A\parking_system\app.py"
```

`setup_recognition.py` 会把识别模型准备到独立演示目录；不会读取或修改默认业务库。关闭该 PowerShell 窗口后，环境变量不会继续影响其他启动会话。

## 一键答辩演示模式

双击仓库根目录的 `一键答辩演示.cmd`。它只会重建受管的
`Module A/parking_system/runtime/defense_demo/parking.sqlite3`，不会覆盖默认业务库，随后以
`test` / `1` 启动系统。程序会自动打开“答辩指引”，按 FR-1～FR-8 和
TC-01～TC-12 给出现场操作、预置车牌与预期结果；最近 30 天的统计数据已准备好。

预置车牌包括：`陕A90002`（3 小时 20 分，11.00 元）、`陕A90003`（免费）、
`陕A90004`（未缴费拦截）、`陕A90005`（授权放行）和 `陕A90009`（26 小时跨天封顶 60.00 元）。
选择图片或视频时仍使用真实 HyperLPR3 识别；识别失败时再使用系统内的人工补录流程。

Windows 便携 ZIP 内另附 `一键演示.cmd` 和预生成的独立演示库模板。完整解压后双击该脚本即可使用
`test` / `1` 登录，不需要安装 Python；每次启动会从模板重置演示库，普通业务库不受影响。
请保留解压得到的英文顶层目录名 `ParkingSystem`，不要把程序所在文件夹改成中文；当前冻结版
QtWebEngine 在中文应用目录中可能于登录后原生退出。

## 可选配置

通过环境变量可调整本地运行行为：

| 环境变量 | 默认值 | 作用 |
| --- | --- | --- |
| `PARKING_DATA_DIR` | `Module A/parking_system/runtime` | 指定数据库、模型与抓拍文件目录 |
| `PARKING_RECOGNITION_THRESHOLD` | `0.80` | 设置识别置信度阈值，范围 `(0, 1]` |
| `PARKING_RECOGNITION_ATTEMPTS` | `3` | 设置识别尝试次数，范围 `1～3` |
| `ANIM_MODE` | `auto` | 选择 `auto`、`webgl`、`video`、`sequence` 或 `placeholder` 动画模式 |

## 测试与自检

运行全部自动化测试：

```powershell
Push-Location "Module A\parking_system"
& "..\..\.venv\Scripts\python.exe" -m pytest -q tests
Pop-Location
```

运行核心业务闭环和动画自检：

```powershell
.\.venv\Scripts\python.exe "Module A\parking_system\tools\selftest_flow.py"
.\.venv\Scripts\python.exe "Module A\parking_system\tools\selftest_anim.py"
```

当前验证结果以 `PROGRESS.md` 的最新恢复入口为准。Phase 4 已用默认规模生成 1000 条演示记录，并渲染检查 30 页中文 PDF 和空数据 PDF；Phase 5 已开始执行真实媒体、准确率和性能验收，未通过项会保留原始结果并继续复测。

## 数据与安全说明

- 默认数据库位置为 `Module A/parking_system/runtime/parking.sqlite3`。
- 测试或演示时可通过 `PARKING_DATA_DIR` 使用独立数据目录，避免污染正式演示数据。
- 数据库、备份、识别模型、抓拍图片、日志、缓存和虚拟环境均不应提交到 Git。
- SQL 操作使用参数化查询；收费金额使用 `Decimal` 处理；重复进场、无进场记录和未缴费放行均有业务校验。

## 已知限制

- 当前只支持从本地图片或视频文件识别，尚未接入实时摄像头。
- 首轮 100 张混合鲁棒性集准确率为 77%，未达到 90%；仍需建立符合“车牌完整、光照正常”口径且不按模型结果挑选的固定准确率集。
- 当前仅完成 3 段真实视频回归，还缺 2 段不少于 10 秒的独立视频；1366×768 完整界面和 TC-01～TC-12 仍需补充验收。

第三方车牌识别方案：[HyperLPR](https://github.com/szad670401/HyperLPR)。
