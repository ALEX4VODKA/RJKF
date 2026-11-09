# 报错与排查记录

## 索引与维护

| 编号 | 问题 | 状态 | 阶段 |
| --- | --- | --- | --- |
| [ERR-001](#err-001) | HyperLPR3 Windows 模型目录 | 已缓解 | Phase 3 |
| [ERR-002](#err-002) | ONNX Runtime 1.31.1 原生 DLL 崩溃 | 已缓解 | Phase 3 |
| [ERR-003](#err-003) | Qt / ONNX 原生 DLL 导入顺序 | 已缓解 | Phase 3 |
| [ERR-004](#err-004) | 首次解压后删除 ZIP 被占用 | 已缓解 | Phase 3 |
| [ERR-005](#err-005) | 工具输出截断导致证据不完整 | 已解决（当次读取） | Phase 0 / 通用操作 |
| [ERR-006](#err-006) | Windows 沙箱进程／临时目录权限 | 已缓解 | Phase 1 |
| [ERR-007](#err-007) | 真实识别后 3D 抬杆长时间锁住车道 | 已解决 | Phase 3 / 4 联调 |
| [ERR-008](#err-008) | 视频固定三点抽帧遗漏清晰车牌窗口 | 已解决 | Phase 5 |
| [ERR-009](#err-009) | Hugging Face 大文件传输中途 EOF | 已解决（本次素材下载） | Phase 5 / 素材准备 |
| [ERR-010](#err-010) | 黄牌批处理触发 NumPy 空切片运行时警告 | 待复现 | Phase 5 / 图片基准 |
| [ERR-011](#err-011) | PyInstaller 冻结版 ONNX 加载顺序与资源遗漏 | 已解决 | Phase 5 / 部署 |
| [ERR-012](#err-012) | 短密码登录失败仅显示行内文字 | 已解决 | Phase 5 / 桌面验收 |
| [ERR-013](#err-013) | 冻结版从中文程序目录启动时登录后原生退出 | 已解决（本机） | Phase 5 / 部署 |

- 同一问题更新原编号，编号不回收。状态使用：待复现／排查中／已缓解／已解决／已失效。
- 区分用户引用、历史任务结果、本次代码检查、本次运行验证。缺失原始日志时写明缺失，不补造堆栈、退出码或实验命令。
- “已缓解”表示已有项目处理与历史成功结果，未必证明底层唯一根因或兼容性问题已永久解决。
- 新问题沿用下列字段：标题/Phase/日期/状态、环境、触发与影响、事实与假设、实验及排除方案、根因、处理位置、验证及复查条件、沉淀位置。
- 错误输出只保留必要片段并脱敏；不存 Token、密钥、完整环境变量或个人目录。完整业务进度见 [PROGRESS.md](PROGRESS.md)。

<a id="err-001"></a>
## ERR-001：HyperLPR3 的 Windows 模型目录

- **阶段、日期、状态**：Phase 3；历史发现/验证日期据进度为 2026-10-28；本次 2026-10-28 静态核对，未重跑；已缓解。
- **环境**：Windows、Python 3.12.8、HyperLPR3 0.1.3；模型放在应用 data_root 下 `.hyperlpr3`，不依赖个人主目录。
- **触发与影响**：首次真实导入解析出无盘符的用户路径，出现权限错误并阻止模型初始化。原始完整异常和退出码未保存。
- **证据来源**：用户引用“默认把模型目录解析成 `\Users...`”；现有 `HyperLprBackend._import_hyperlpr()` 注释说明该版本读取 HOMEPATH；历史 Phase 3 记录说明路径问题已处理。
- **事实/假设**：已看到代码在导入期间暂存并定向 HOMEPATH，finally 恢复原值，并向 LicensePlateCatcher 显式传入 folder。不能把这写成依赖库支持某个未经验证的专用模型环境变量。
- **排查与根因**：历史结论为第三方 Windows 路径处理问题；本次未独立读取已安装依赖源码或重现，原始实验序列及排除方案未记录。
- **解决位置**：`Module A/parking_system/parking/recognition/service.py` 的 `_import_hyperlpr()` 与构造方法；提交 `25bbd9f7`。
- **验证与边界**：历史官方样例推理成功，详见 PROGRESS.md Phase 3；需在干净环境下分别核对首次安装、模型就绪后的离线启动、环境变量恢复。升级 HyperLPR3 或改变数据路径后重新验证，不直接删除适配。
- **沉淀**：[AGENTS.md](AGENTS.md) 第 7 节记录项目目录约束；未更新全局 Skill。

<a id="err-002"></a>
## ERR-002：ONNX Runtime 1.31.1 原生 DLL 崩溃

- **阶段、日期、状态**：Phase 3；据历史记录首次发现及成功验证为 2026-10-28；本次仅静态核对；已缓解。
- **环境**：当前 Windows / Python 3.12.8；HyperLPR3 0.1.3；失败版本记录为 onnxruntime 1.31.1，当前锁定 1.26.0。
- **触发与影响**：真实推理排查期间导入原生 DLL 发生访问冲突，可能直接终止进程，不能假定 Python try/except 能捕获。原始退出码及完整堆栈未保存。
- **证据来源**：用户提供的历史对话；`requirements.txt` 中的版本锁定及注释；PLANT.md 迁移的 Phase 3 成功推理记录。
- **事实/假设**：版本锁定存在；历史记录表明 1.26.0 配合现有启动顺序可用。不能据此断定仅版本导致崩溃，DLL 导入顺序也是相关变量，见 ERR-003。
- **实验与根因**：历史曾更换运行时并验证，完整版本矩阵及单变量实验未保存；底层唯一根因尚未确认。不用“与依赖年代更匹配”代替兼容性证据。
- **解决位置**：`Module A/parking_system/requirements.txt`，提交 `25bbd9f7`；保留当前经历史验证的组合。
- **验证与边界**：历史 57 passed 及真实样例结果不等于所有环境兼容。升级时在独立子进程中记录解释器、版本、导入顺序、退出码，验证冷启动与真实推理；此处是后续验证方法，本次未执行。
- **沉淀**：[AGENTS.md](AGENTS.md) 第 7 节规定依赖升级先验证；未提升为全局 Windows 版本禁令或 Skill。

<a id="err-003"></a>
## ERR-003：PyQt5 与 ONNX Runtime 导入顺序

- **阶段、日期、状态**：Phase 3；历史发现/验证日期据进度为 2026-10-28；本次静态核对；已缓解。
- **环境**：当前 Windows、Python 3.12.8、PyQt5 5.15.11、HyperLPR3 0.1.3、锁定的 ONNX Runtime 组合。
- **触发与影响**：历史二分结果为 `PyQt5 → onnxruntime` 失败，`onnxruntime → PyQt5` 稳定；可能表现为 DLL 初始化失败。完整报错、退出码和二分脚本未保存。
- **证据来源**：用户明确引用上述二分结论；`app.py` 在 Qt 前导入 ONNX；后端也提前导入 ONNX 并有说明。
- **事实/假设**：代码入口顺序已固定；历史结论支持顺序相关性，但具体 DLL 冲突机制尚未确认，不能推广到所有 Windows 环境。
- **实验及排除方案**：已知历史比较了两种导入顺序；未记录重复次数、完整控制变量或其他排除方案。不能将后端预导入理解为可补救任何已加载 Qt 的进程状态。
- **解决位置**：`Module A/parking_system/app.py` 与 `parking/recognition/service.py`；提交 `25bbd9f7`。新 GUI 入口也应遵守经验证的加载顺序。
- **验证与边界**：历史独立 app 冷启动推理成功；升级后使用独立子进程分别检查入口顺序、Qt 初始化和真实推理，记录返回码，不在主应用里反复触发原生崩溃。本次未执行。
- **沉淀**：[AGENTS.md](AGENTS.md) 第 7 节保留项目入口约束；未修改全局 Skill。

<a id="err-004"></a>
## ERR-004：首次解压模型后的 ZIP 文件占用

- **阶段、日期、状态**：Phase 3；据历史进度发现/验证为 2026-10-28；本次静态核对；已缓解。
- **环境**：Windows、HyperLPR3 0.1.3，首次模型下载/解压路径。
- **触发与影响**：解压后在 ZIP 句柄关闭前删除文件；现有注释记录 WinError 32。原始完整异常、退出码和依赖源码证据未留存。
- **证据来源**：`_import_hyperlpr()` 注释及历史 Phase 3 的 ZIP 问题修复说明；不是本次重现。
- **事实/假设**：代码捕获 PermissionError 后，只有 `_models_ready()` 确认所需文件存在才清理半导入模块并重试，否则抛明确错误。此检查仅确认文件存在，不等同模型内容校验；当前捕获范围不只 WinError 32，不宣称做了精确错误码过滤。
- **排查与根因**：历史归因为 Windows 文件句柄占用；完整实验及排除方案未记录，本次未独立验证第三方句柄生命周期。
- **解决位置**：`Module A/parking_system/parking/recognition/service.py` 的 `_import_hyperlpr()`、`_models_ready()`，提交 `25bbd9f7`。
- **验证与边界**：已有历史初始化与推理成功记录；干净目录首次下载、模型不完整、已有模型离线重启仍应分别验证。依赖升级后确认是否仍需重试；不为测试清空用户实际模型目录。
- **沉淀**：详细处理仅保留本记录，AGENTS.md 通过环境问题索引引用；未修改 Skill。

<a id="err-005"></a>
## ERR-005：工具输出截断导致证据不完整

- **阶段、日期、状态**：Phase 0 / 文档读取；首次为本任务历史 2026-10-27，恢复核对为 2026-10-28；当次读取问题已解决，仍属持续防范事项。
- **环境**：PowerShell、exec_command 返回输出及外层工具输出预算。
- **触发与影响**：同时输出大量 UI 源码或三份 DOCX 的全部段落，出现 `Warning: truncated output` 及 `tokens truncated`，无法证明全文已读。2026-10-30 Phase 4 首次 pytest setup 失败输出也被外层截断。Shell 正常退出不能证明输出完整。
- **证据来源**：本对话早前工具结果直接包含截断标记；后续使用文件范围和关键词定向读取计费、事务、统计及 UI 交互段落。
- **事实/假设**：这些调用是输出量超过预算，不能据此认定源文件损坏。PowerShell 表格省略、长行裁剪与工具截断应分别辨认。
- **排查与处理**：先用 rg 找位置，再按文件/行段或结构化字段分批读取；检查末尾或结束标记，直到目标范围完整。仅提高单层预算可能仍遇外层截断，不作为唯一办法。
- **验证与边界**：原任务对关键段落的定向返回已无截断；Phase 4 缩小输出后确认所有 setup 错误均指向同一临时目录权限问题，并在沙箱外获得完整测试结果。未重新完整读取全部设计文档，也未声称已读全文。以后发现截断，记录已读范围及待补范围，补齐前不据此作完整性结论。
- **沉淀**：[AGENTS.md](AGENTS.md) 第 7 节要求截断后重读；现有 windows-local-ops 已有分段读取规范，本次不重复修改 Skill。

<a id="err-006"></a>
## ERR-006：Windows 沙箱进程／临时目录权限

- **阶段、日期、状态**：Phase 1；历史发现与验证记录日期 2026-10-28；本次仅迁移证据；已缓解。
- **环境**：Codex Windows 沙箱、项目 Python 3.12.8；pytest 临时目录与 Qt WebEngine 进程路径。
- **触发与影响**：历史 P1-A 记录为 WebGL 与 pytest 遭遇进程/临时目录 ACL 限制。2026-10-30 Phase 4 在沙箱内运行 pytest 时，默认临时目录与显式工作区 `--basetemp` 均在 fixture setup 阶段报 `PermissionError: [WinError 5]`，业务断言未执行；完整历史 P1-A 命令仍未保存，不补造。
- **证据来源**：PLANT.md 迁移的 P1-A 验证记录；原文称改在沙箱外执行后通过，代码断言无失败。
- **事实/假设**：存在历史不同执行环境下通过的报告；不能仅因处于沙箱就认定所有失败都是权限问题，具体 ACL 根因尚缺原始证据。
- **实验与解决**：Phase 4 先换用工作区内全新 `--basetemp` 并关闭 pytest 缓存，仍复现相同 ACL 拒绝；随后按当前审批机制在沙箱外使用相同解释器和测试命令运行。未修改系统 ACL、环境变量或全局 pytest 配置。
- **验证与边界**：2026-10-30 沙箱外 Phase 4 聚焦测试先为 8 passed，最终全量为 92 passed in 5.17s；这证明当前代码断言通过，不等于底层沙箱 ACL 根因已解决。环境、解释器或临时目录变化后重新核对。
- **沉淀**：[AGENTS.md](AGENTS.md) 第 7 节要求区分环境与断言失败；通用操作已有 windows-local-ops，证据不足以新增全局修复规则。

<a id="err-007"></a>
## ERR-007：真实识别后 3D 抬杆长时间锁住车道

- **阶段、日期、状态**：Phase 3 / 4 联调；2026-11-02；已解决。
- **环境**：Windows、Python 3.12.8、PyQt5/PyQtWebEngine、真实 HyperLPR3 图片识别、`parking.glb` 模型与高分辨率主窗口。
- **触发与影响**：用户报告识别进场并成功写库后，场景长期停在“入口 · 抬杆中…”，四个车道入口按钮保持禁用，无法继续业务流程。数据库只读核对确认对应记录已保存为在场、未计费、未放行，说明识别与登记事务没有丢失，卡点在动画完成状态迁移。
- **事实与排除**：独立 viewer 在普通及 834×1027 窄高视口均收到 `focus → action → finished`；单实例整窗口 WebGL 也能完成抬杆和落杆，排除模型文件必然损坏。使用同一抓拍图、真实识别线程、临时数据库和真实 WebGL 的组合测试可完成，但识别成功到抬杆完成约 6.75 秒，明显超过配置注释期望的约 2.7 秒（镜头 0.9 秒 + 动作 1.8 秒）。用户当次漏回调未在重启后的单实例中稳定复现，因此不把缓存、显卡或桥接中的任一项写成唯一根因。
- **根因与处理**：`viewer.js` 虽按 `duration / 1.8s` 计算倍速，却又把倍速封顶为 8，长时间轴模型无法真正压到 1.8 秒；渲染循环还把每帧推进量封顶为 50 ms，低帧率时会进一步按帧数拖长。已移除最大倍速限制并把低帧率推进上限放宽到 250 ms。`ScenePanel` 原来只依赖具体动画器的回调/看门狗；现增加 12 秒上层操作超时，若动画实现漏发 `finished/failed`，会退出无限等待并明确提示刷新重试，仍不伪造闸杆已抬起。
- **验证与边界**：工作目录 `Module A/parking_system`，解释器 `F:\2026\RJKF\.venv\Scripts\python.exe`。聚焦 `tests/test_phase2_ui.py` 为 4 passed；全量 pytest 为 93 passed in 4.69s；`tools/viewer_test.py` 收到完整事件并 PASS；加强后的 `tools/selftest_webgl.py` 明确等待并确认“入口已抬起 → 入口待机”，结果 WEBGL PASS。2026-11-02 用户随后确认修复后桌面复验“已完成”；本次未另存复验截图或操作日志，不把该确认扩大为 Phase 4 全部验收完成。
- **沉淀**：本项目排错保留在本条及 [PROGRESS.md](PROGRESS.md)；未把单项目 GLB 时长经验提升为全局 Skill。

<a id="err-008"></a>
## ERR-008：视频固定三点抽帧遗漏清晰车牌窗口

- **阶段、日期、状态**：Phase 5；2026-11-06；已解决。
- **环境**：Windows、Python 3.12.8、HyperLPR3 0.1.3、ONNX Runtime 1.26.0；项目现有 `LicenseRecognizer`；LSV-LP 官方小样本转换的 H.264、25 FPS、300 帧、12 秒视频。
- **触发与影响**：三段真实视频中两段自动识别并与官方 JSON 标注精确一致，竖屏跟拍序列返回“未检测到有效车牌”。当前 `_video_attempts()` 对 300 帧视频固定读取 0 基帧号 74、149、224；对应画面分别明显运动模糊、没有车辆、车牌位于边缘且模糊，因此真实视频验收会受偶然抽帧位置影响。
- **证据与排除**：三个 MP4 均经 ffprobe 确认可解码且为 300 帧；失败序列第 100 帧画面车牌清晰，单独作为图片交给同一识别器时以 0.9885 置信度识别，并与该帧官方标注精确一致，耗时 1660 ms。因此已排除视频损坏、模型完全不支持该车牌或标注缺失；问题集中在视频帧选择，不把该结论扩大为所有视频失败的唯一原因。
- **根因**：`parking/recognition/service.py::_video_attempts()` 使用 `np.linspace` 仅选择 25%、50%、75% 三个固定位置，没有考虑车辆在视频中的出现窗口和帧清晰度；本样本的有效清晰窗口位于固定采样点之间。
- **解决位置与方法**：`parking/recognition/service.py` 先把视频按时间分为前、中、后三段，每段均匀读取五个低成本候选，以降采样灰度图的拉普拉斯方差、曝光和对比度综合评分选择一帧，再交给 HyperLPR；保持最多三次实际模型推理，不使用数据集标注参与选帧，也没有为单个样本硬编码帧号。`tests/test_recognition.py` 使用可控候选帧验证时间覆盖和清晰帧优先。
- **验证与边界**：三段 LSV-LP 视频优化后全部自动识别，并逐段与所选帧官方 JSON 标注精确一致；置信度分别为 0.9988、0.9998、0.9999，耗时分别为 3133 ms、1665 ms、4504 ms。聚焦测试 6 passed in 0.16s，全量 94 passed in 5.00s，均使用项目 `.venv` 在沙箱外运行；沙箱内首次聚焦测试仅因 ERR-006 的临时目录 ACL 在 setup 阶段失败，未执行断言。当前只验证三段样本，仍需用最终五段视频确认泛化；画面质量评分不等同车牌检测，不能保证任意视频必然命中。
- **沉淀**：仅记录在本项目 ERRORS/PROGRESS；尚未形成跨项目通用规则。

<a id="err-009"></a>
## ERR-009：Hugging Face 大文件传输中途 EOF

- **阶段、日期、状态**：Phase 5 素材准备；2026-11-06；本次素材下载已解决。
- **环境**：Windows、PowerShell 7.6.5、Python 3.12.8 `requests` 2.34.2；Hugging Face `resolve` 地址重定向至 Xet/AWS CDN；目标文件为约 908 MB 的 CCPD2020 ZIP 和约 1.6 GB 的 CRPD WebDataset TAR。
- **触发与影响**：Python 流式读取 CRPD TAR 在 CDN 重定向后报 `SSL: UNEXPECTED_EOF_WHILE_READING`；PowerShell 单连接下载 CCPD2020 ZIP 也报 `Received an unexpected EOF or 0 bytes from the transport stream`，目标 ZIP 未生成。小型 API/JSON 请求及 1 MB HTTP Range 请求可成功，说明不是数据集入口整体不可达。
- **处理**：CCPD2020 改为 64 MB HTTP Range 分块，每块校验期望长度并最多重试四次，全部分块完成后按顺序合并；CRPD 只下载归档前 400 MB 范围，结合已取得的人工标注，从该范围内 97 个不同黄牌标签中筛选并提取 20 张，不下载完整 TAR。未关闭 TLS 校验，未把失败片段当作成功文件。
- **验证与边界**：CCPD2020 合并文件长度为 907711344 字节，`zipfile.ZipFile.testzip()` 返回 `None`，归档包含 11776 个文件；20 张绿牌已从该 ZIP 提取。CRPD 范围片段可顺序读取 657 个 TAR 成员，其中 99 个黄牌标注、97 个不同文本，最终提取 20 张并人工查看。该处理只证明当前公开素材下载完成，不代表 Hugging Face/CDN 的底层连接问题永久消失。
- **沉淀**：保留在本项目 ERRORS；下载脚本和分块缓存位于被 Git 忽略的 `res/phase5_images/_sources/`。这是一次数据源与网络组合问题，未修改全局 `windows-local-ops` Skill。

<a id="err-010"></a>
## ERR-010：黄牌批处理触发 NumPy 空切片运行时警告

- **阶段、日期、状态**：Phase 5 图片基准；2026-11-06；待复现。
- **环境**：Windows 11、Python 3.12.8、HyperLPR3 0.1.3、ONNX Runtime 1.26.0、NumPy 2.5.4、OpenCV 4.14.0.94；固定 100 张混合鲁棒性图片。
- **触发与影响**：两次沙箱外真实批处理均在进度 90/100 至 100/100 之间输出 `RuntimeWarning: Mean of empty slice` 与 `invalid value encountered in scalar divide`，来源栈停在 NumPy `fromnumeric.py` / `_methods.py`。两次运行都继续完成 100 张并写出完整 CSV/JSON；当前未确认警告对应的具体图片、HyperLPR 内部调用点或是否改变该张候选排序。
- **已确认与边界**：警告在相同黄牌尾段重复出现，因此不是一次性工具截断；验收工具自身未调用 NumPy `mean`，但尚无逐张警告捕获证据，不能据此把根因直接写成 HyperLPR 缺陷。准确率 77/100 的结论不依赖该警告是否存在，因其他失败样本已有明确整牌不一致结果。
- **下一步**：只重放黄牌 91～100，并把运行时警告逐张捕获为诊断记录，定位具体样本和调用栈；不得通过全局忽略 NumPy 警告掩盖问题。

<a id="err-011"></a>
## ERR-011：PyInstaller 冻结版 ONNX 加载顺序与非 Python 资源遗漏

- **阶段、日期、状态**：Phase 5 部署；2026-11-09；已解决（本机 Windows 11 x64）。
- **环境**：Windows 11、Python 3.12.8、PyInstaller 6.22.3、PyQt5 5.15.11、PyQtWebEngine 5.15.7、ONNX Runtime 1.26.0、HyperLPR3 0.1.3；构建形态为 `onedir`。
- **触发与影响**：首个便携包包含 ONNX DLL、QtWebEngine 和模型文件，但启动 `--verify-installation` 时 `onnxruntime_pybind11_state` 报 DLL 初始化失败；保留源码入口“先 ONNX、后 PyQt”仍不足，因为 PyInstaller 的 `pyi_rth_pyqt5` 在 `app.py` 前执行。修复后安装自检通过，但普通 GUI 首次冷启动又在数据库初始化时报包内缺少 `parking/data/schema.sql`，导致程序在登录界面前退出。
- **证据与排除**：源码环境的锁定组合此前可运行；首包逐项确认 `onnxruntime.dll`、pybind pyd、QtWebEngineProcess、3D 场景和四个模型文件存在，因此不是单纯漏复制 ONNX 文件。构建日志确认自定义钩子排在 `pyi_rth_pyqt5` 之前；加入后安装自检可以继续执行并真实加载识别模型。普通启动新增的 `runtime/startup-error.log` 给出 `Database.initialize()` 读取 `_internal/parking/data/schema.sql` 的明确 FileNotFoundError，排除登录逻辑或 SQLite 写权限为当次根因。
- **解决位置与方法**：`tools/pyi_rth_onnxruntime_first.py` 在 Qt 运行时钩子之前导入 ONNX；`parking_system.spec` 显式收集 `schema.sql`、viewer 和 resources，并排除 Torch/Matplotlib/pytest 等非运行依赖；`app.py` 区分 `_internal` 只读资源目录与 exe 同级可写目录，将数据库、抓拍和 WebEngine 缓存定向 `runtime/`，提供 `--verify-installation` 与窗口版启动错误日志；`tools/build_windows.py` 复制本地模型并生成 ZIP 和哈希。
- **验证与边界**：最终包安装自检退出码 0，报告 QtWebEngine 与离线识别模型 ready；普通 GUI 隐藏冷启动 8 秒仍驻留，SQLite 已创建且无启动错误日志。认证修复后的最终 ZIP `testzip()` 无坏项、316857577 字节，SHA-256 为 `bfe858f99bb874cd7a080dcaedd6ad4fca000f4452f581cd23868dc5cbddb33d`；全量 pytest 101 passed in 5.76s。当前仅在构建机 Windows 11 x64 验证，第二台 Windows 10/11 目标机仍需最终部署验收。
- **沉淀**：该顺序是本项目当前 PyQt5/ONNX 组合的已验证约束，与 ERR-003 一致；不推广为所有 PyInstaller/Qt/ONNX 版本的通用结论。

<a id="err-012"></a>
## ERR-012：短密码创建/登录失败仅显示行内文字，用户感知为无响应

- **阶段、日期、状态**：Phase 5 桌面验收；2026-11-09；已解决。
- **现象与影响**：用户在打包程序点击登录后看不到后续窗口，也没有弹窗。认证对话框原实现会把 `AuthenticationError` 只写到窗口底部的红色标签；首次创建使用少于 8 个字符的密码时，服务层立即拒绝，但按钮、窗口和焦点均无明显变化，因此容易被理解为按钮失效。
- **根因**：`AuthService._validate_credentials()` 与 `change_password()` 强制至少 8 个字符；`AuthDialog._submit()` 捕获错误后仅调用 `QLabel.setText()`，没有模态提示。按钮连接本身正常，不是信号未绑定或数据库事务挂起。
- **解决位置与方法**：按用户明确的纯测试用途，`parking/services/admin_service.py` 取消首次管理员、后续账号创建和改密的密码长度/字符限制，允许空密码并继续使用 PBKDF2 加盐存储；用户名规则保持不变。`parking/ui/auth_dialog.py` 更新占位提示，创建或登录失败时同时保留行内文字并显示 `QMessageBox.warning`。
- **验证与风险**：聚焦认证/UI 测试 18 passed in 1.35s，全量 101 passed in 5.76s；自动覆盖空密码创建和登录、单字符密码登录、中文/空格/符号密码、改密及错误密码弹窗。重建包安装自检和 GUI 冷启动通过。允许空密码会显著降低安全性，只适用于当前课程本地测试程序；若转为真实部署，应恢复密码策略。

<a id="err-013"></a>
## ERR-013：冻结版从中文程序目录启动时登录后 QtWebEngine 原生退出

- **阶段、日期、状态**：Phase 5 部署；2026-11-09；已解决（本机构建机）。
- **环境与现象**：Windows 11 24H2、PyInstaller 6.22.3、PyQt5 5.15.11、PyQtWebEngine 5.15.7。冻结版在 `…\智慧停车收费系统\智慧停车收费系统.exe` 中输入 `admin / 1` 后，认证窗口关闭但主窗口不出现。SQLite 操作日志连续记录 `login.success`，运行目录没有 Python `startup-error.log`。
- **证据与根因**：Windows Application Error 事件 1000 连续三次指向 `Qt5Core.dll` 5.15.2.0，异常代码 `0xc0000409`、偏移 `0x204e8`；进程退出码为 `-1073740791`。同一 EXE 使用 `ANIM_MODE=placeholder` 时主窗口正常，确认崩溃发生在 QtWebEngine 3D 初始化。软件 OpenGL、英文 EXE 文件名、外置数据目录均不能消除故障；旧 `console=False` EXE 不改代码，仅将完整程序复制到纯英文 `ParkingSystem\` 目录后，自动输入同一账号可稳定显示“智慧停车 · 出入口控制台”。反向把已通过的候选 EXE 放回中文应用目录又复现同一退出码。因此本环境的直接触发条件是冻结版 QtWebEngine 从中文应用目录初始化，而不是认证、SQLite、密码或 EXE 显示名称。
- **解决位置与方法**：`parking_system.spec` 的 `COLLECT` 输出目录改为 ASCII `ParkingSystem`；`tools/build_windows.py` 将内部程序目录名与中文 ZIP 展示名分离。ZIP 仍使用中文名称，界面及 EXE 文件名不变，完整解压后实际运行路径为 `ParkingSystem\智慧停车收费系统.exe`。新增 `tests/test_package_spec.py` 防止打包目录回退为中文。
- **验证与边界**：正式构建目录中自动登录 `admin / 1` 后进程持续运行并显示“智慧停车 · 出入口控制台”；一键演示模式使用 `test / 1` 后进程同样持续运行。安装自检退出码 0，报告 `webengine=true`、`recognition_model=ready`。正式 ZIP 根目录只有 `ParkingSystem`，包含离线模型和演示模板，不含测试数据库、缓存或日志；317107252 字节，SHA-256 为 `B443C64788C455A19D2B9E71D0D4A678F314A09A3624D786054BD11C9531D449`。本次只在构建机验证，第二台 Windows 仍需回归；不能把该约束推广为所有 QtWebEngine 版本的普遍问题。
