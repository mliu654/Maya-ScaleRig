# Maya ASCII 绑定文件整体放大逻辑总结

## 目标

目标不是在角色外面套一个 `scale = 2.5` 的组，也不是把主控制器的 `scaleX/Y/Z` 改成 `2.5`，而是把 `.ma` 文件里的“场景空间长度数据”统一改成新的单位尺寸。

最终效果应接近：

```text
角色真实尺寸变为 2.5 倍
主控 / 控制器 scale 通道仍保持 1,1,1
Geometry / MotionSystem / DeformationSystem 顶层 scale 通道仍保持 1,1,1
ADV Rebuild 后不会因为外部 proxy / 父级 scale 被清掉而回到旧尺寸
```

核心原则：

```text
只缩放“长度、位置、空间距离”
不缩放“比例、旋转、权重、法线、UV、颜色、开关、UI 滑块范围”
```

---

## 为什么不能直接全文件乘 2.5

`.ma` 是文本文件，但里面的数字并不都是空间距离。

如果全局把所有数字乘以 `2.5`，会同时改到：

```text
scale 通道
rotation / jointOrient
skin weights
blendShape 权重
UV
normal
颜色
visibility
IK pole vector 方向
face panel 的 -1 到 1 UI 滑块范围
各种 ratio / clamp / bool / enum
```

这些值不是“长度”。它们一旦被改，绑定会出现扭曲、表情过大、IK 拉爆、权重错误等问题。

---

## 最终成功方案的逻辑

### 1. 放大模型点位

需要缩放 mesh 顶点：

```mel
setAttr ".vt[...]" ...
```

这会让模型本身的原始点位变为 2.5 倍，而不是通过 transform scale 放大。

### 2. 放大骨骼和 transform 的位移

需要缩放：

```mel
setAttr ".t" -type "double3" x y z;
setAttr ".tx" value;
setAttr ".ty" value;
setAttr ".tz" value;
```

还要缩放 pivot / rotatePivotTranslate / scalePivotTranslate 等空间偏移值：

```mel
.rp
.sp
.rpt
.spt
.tp
```

这些都是空间位置或偏移。

### 3. 同步放大 bindPose / bindPreMatrix / dagPose 里的矩阵位移

模型扭曲的核心原因通常是：

```text
mesh 点位和 joint translate 被放大了
但 skinCluster / bindPose 里的矩阵位移还停留在旧尺寸
```

所以要处理：

```mel
setAttr ".pm[...]" -type "matrix" ...
setAttr ".bm" -type "matrix" ...
setAttr ".m"  -type "matrix" ...
```

普通 4x4 matrix 只缩放 translation 部分：

```text
第 12、13、14 个数值
```

`matrix "xform"` 格式只缩放其中的线性空间项：

```text
translate
scalePivot
scalePivotTranslation
rotatePivot
rotatePivotTranslation
```

不缩放 matrix 里的旋转、scale basis、quaternion、inverseParentScale。

### 4. 放大控制器曲线 / 面部曲线 / nurbsSurface 的 CV

控制器和 face rig 里有大量 nurbsCurve / nurbsSurface 数据：

```mel
setAttr ".cc" -type "nurbsCurve" ...
setAttr ".cc" -type "nurbsSurface" ...
```

这些数据里既有 knot、degree、form，也有 CV 坐标。

只应该缩放 CV 的 XYZ 坐标，不应该缩放：

```text
degree
spans
form
knot values
rational weight
```

### 5. 放大自定义空间属性

ADV rig 里有一些自定义长度属性，例如：

```text
height
fat
fatYabs
fatFrontAbs
fatWidthAbs
falloffRadius
radius
```

这些如果是 `addAttr -dv` 默认值，也要跟着放大。

### 6. 修复 ADV 的 IK / Stretch 旧长度缓存

你测试中出现的最后一个问题是：

```text
模型整体正常
切到 IK 时胳膊、腿被拽到 IK 上
```

这不是 mesh / skin 本身的问题，而是 ADV 生成出来的 IK 测距和 stretch 网络里还保存了旧长度。

典型节点包括：

```text
IKmessureDivArm_R.input2X
IKmessureDivArm_L.input2X
IKmessureDivLeg_R.input2X
IKmessureDivLeg_L.input2X
IKdistanceClampArm_R.maxR
IKdistanceClampArm_L.maxR
IKdistanceClampLeg_R.maxR
IKdistanceClampLeg_L.maxR
IKXElbow_R_IKLenght_R.input2X
IKXWrist_R_IKLenght_R.input2X
IKXKnee_R_IKLenght_R.input2X
IKXAnkle_R_IKLenght_R.input2X
```

如果这些值还停在旧尺寸，IK 网络会认为：

```text
当前距离 / 旧长度 = 2.5
```

于是会触发错误拉伸。

解决方式是：

```text
识别名字里带 distance / length / lenght / measure / messure / stretch / normalize 的 utility 节点
只缩放它们代表 rest length 的第一个数值
不要把后面的 ratio 1,1 也乘掉
```

### 7. 放大 ADV IK distance 的 animCurveUU 曲线

ADV 的 IK distance / antiPop 网络里有一些 `animCurveUU`，虽然类型是 unitless，但是曲线名和用途表明它们两边都是距离值：

```text
IKdistanceArm_RShape_normal
IKdistanceArm_RShape_antiPop
IKdistanceLeg_RShape_normal
IKdistanceLeg_RShape_antiPop
```

这些 `.ktv[]` 里的输入距离和输出距离都要乘 2.5。

否则 IK 控制器距离已经变大，但曲线还按旧角色尺寸判断，会导致切 IK 时拉伸异常。

### 8. 保护右侧 face panel 的 UI 滑块范围

你遇到“表情幅度变大”的原因，主要是上一版误放大了 transform translate limit：

原始：

```mel
setAttr ".mntl" -type "double3" -1 -1 0;
setAttr ".mxtl" -type "double3"  1  1 0;
```

错误放大后：

```mel
setAttr ".mntl" -type "double3" -2.5 -2.5 0;
setAttr ".mxtl" -type "double3"  2.5  2.5 0;
```

这些在 face panel 上通常不是世界空间距离，而是 UI 滑块范围。

因此最终脚本默认不缩放：

```text
.mntl
.mxtl
```

如果某个特殊 rig 的 translate limit 真的是空间限制，可以手动开启脚本参数：

```cmd
--scale-translate-limits
```

### 9. SDK 曲线的处理

`animCurveUL` 的含义通常是：

```text
unitless input -> linear output
```

也就是输入可能是 face slider 的 `-1 ~ 1`，输出是某个 translate 位移。

最终成功版本采用的逻辑是：

```text
face slider 输入范围不变
animCurveUL 的输出位移按 2.5 放大
```

这样表情控制器还是原来的操作范围，但真正驱动到脸上的空间位移会适配放大后的角色。

如果某个 rig 的 SDK 输出并不是空间位移，而是自定义比例值，可以关闭：

```cmd
--sdk-mode none
```

---

## 最终脚本推荐命令

针对这次 ADV 文件，推荐：

```cmd
$env:PYTHONPATH=".\src"; python -m maya_scalerig .\tests\fixtures\input.ma .\output_2p5.ma 2.5 --preset adv --sdk-mode linear-output --report .\output_2p5_report.txt
```

由于脚本默认就是 ADV profile，也可以简写为：

```cmd
$env:PYTHONPATH=".\src"; python -m maya_scalerig .\tests\fixtures\input.ma .\output_2p5.ma 2.5 --report .\output_2p5_report.txt
```

更保守的通用 rig 模式：

```cmd
$env:PYTHONPATH=".\src"; python -m maya_scalerig .\tests\fixtures\input.ma .\output_2p5.ma 2.5 --preset generic --sdk-mode none --report .\output_2p5_report.txt
```

如果文件里已有 translate 动画 key，并且希望位移动画也适配新尺寸：

```cmd
$env:PYTHONPATH=".\src"; python -m maya_scalerig .\tests\fixtures\input.ma .\output_2p5.ma 2.5 --preset adv --sdk-mode linear-output --scale-linear-animation --report .\output_2p5_report.txt
```

安装为本地命令后，也可以把上面的 `python -m maya_scalerig` 换成 `maya-scalerig`。

---

## Maya 内测试清单

打开输出文件后，先不要覆盖原文件。建议按顺序检查：

```python
import maya.cmds as cmds

for node in ["Group", "FitSkeleton", "MotionSystem", "MainSystem", "Main", "DeformationSystem", "Geometry"]:
    if cmds.objExists(node):
        print(node, cmds.getAttr(node + ".scale")[0])
```

这些顶层 scale 理想情况下仍应接近：

```text
1, 1, 1
```

检查尺寸：

```python
import maya.cmds as cmds

if cmds.objExists("Geometry"):
    bbox = cmds.exactWorldBoundingBox("Geometry")
    print("height:", bbox[4] - bbox[1])
```

检查 face panel translate limit 是否没有被放大：

```python
import maya.cmds as cmds

for node in ["ctrlBrow_R", "ctrlBrow_L", "ctrlEye_R", "ctrlEye_L", "ctrlMouth_M"]:
    if cmds.objExists(node):
        print(node)
        print("  min:", cmds.getAttr(node + ".mntl")[0])
        print("  max:", cmds.getAttr(node + ".mxtl")[0])
```

检查 IK rest length 是否被放大：

```python
import maya.cmds as cmds

attrs = [
    "IKmessureDivArm_R.input2X",
    "IKmessureDivArm_L.input2X",
    "IKmessureDivLeg_R.input2X",
    "IKmessureDivLeg_L.input2X",
    "IKdistanceClampArm_R.maxR",
    "IKdistanceClampArm_L.maxR",
    "IKdistanceClampLeg_R.maxR",
    "IKdistanceClampLeg_L.maxR",
]

for attr in attrs:
    if cmds.objExists(attr):
        print(attr, cmds.getAttr(attr))
```

功能测试：

```text
FK 手臂 / 腿
IK 手臂 / 腿
IK/FK 切换
Stretch / antiPop
space switch
脸部表情面板
眼球、牙齿、眉毛、头发、衣服
ADV Rebuild
FBX / 引擎导出，如项目需要
```

---

## 常见问题判断

### 打开文件后模型扭曲，但 ADV Rebuild 后正常

通常说明：

```text
源空间数据已经基本放大成功
但 Build 后生成的 utility / rest length / IK normalize 缓存还没同步放大
```

解决方向：

```text
开启 --preset adv
确认 rest constants 被缩放
检查报告里的 rest_length_utility_first_values
检查 IKdistance animCurveUU 是否被缩放
```

### 表情面板幅度过大

通常说明：

```text
face slider 的 .mntl / .mxtl 被放大了
或者 SDK 输出不是空间位移却被放大了
```

解决方向：

```cmd
不要开启 --scale-translate-limits
必要时使用 --sdk-mode none
```

### 切 IK 时胳膊 / 腿被拉爆

通常说明：

```text
IK measure divisor、clamp maxR、length multiplyDivide 或 IKdistance animCurveUU 还停留在旧长度
```

解决方向：

```text
使用 --preset adv
检查报告里是否有：
rest_length_utility_first_values
adv_IKdistance_animCurveUU_key_numbers
```

如果某个自定义 rig 命名不同，可以添加：

```cmd
--extra-rest-regex "你的节点命名关键词"
```

---

## 适配所有绑定的现实边界

这个方法已经比简单改 `translate`、简单套父级 scale、或者 proxy 重连更接近“真正改文件单位尺寸”。

但不存在一个文本脚本可以 100% 自动判断所有 rig 的所有数字含义。风险主要来自：

```text
自定义插件节点
expression / scriptNode 字符串里的长度常量
外部 reference
缓存文件
自定义 build 脚本
特殊命名的 utility 节点
把空间值存在 unitless 自定义属性里的 rig
```

因此脚本提供了可调参数：

```text
--preset adv / generic
--sdk-mode auto / none / linear-output
--rest-mode auto / off / on
--extra-vector-attr
--extra-scalar-attr
--extra-addattr-name
--extra-rest-regex
--scale-translate-limits
--scale-linear-animation
```

通用原则仍然是：

```text
先用保守规则处理
再根据 Maya 打开后的问题补充 specific rule
最后把 specific rule 收敛进脚本参数或 profile
```
