"""PyInstaller 运行时钩子：必须先于 PyQt5 的运行时钩子加载 ONNX Runtime。

源码入口中的导入顺序无法早于 PyInstaller 自动生成的 Qt 运行时钩子，因此冻结
版本需要在这里保留项目已验证过的 Windows 原生 DLL 加载顺序。
"""

import onnxruntime  # noqa: F401
