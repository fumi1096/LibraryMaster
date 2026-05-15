# RDK X5 Ubuntu Server HDMI 显示器配置指南

## 问题描述

使用 RDK X5 安装官方 Ubuntu Server 系统后，HDMI 接口连接的显示器无法识别，显示"无信号"。

## 环境信息

| 项目 | 详情 |
|------|------|
| 硬件 | RDK X5 |
| 系统 | Ubuntu Server 22.04 (Jammy) |
| 内核 | 6.1.83 |
| HDMI 芯片 | SiI9022 (I2C 地址 0x3b, bus 7) |
| DRM 驱动 | vs-drm (VeriSilicon) |
| 显示器 | QDtech MPI7002 / MPI7003 (触摸屏), 首选分辨率 1024x600@60Hz |
| 触摸屏 USB ID | 0483:5750 (STMicroelectronics), 驱动: hid-multitouch |
| 触摸输入设备 | /dev/input/event1 |

---

## 根因分析

### 问题链路

```
HDMI 显示器插入
    ↓
SiI9022 HPD (热插拔检测) 失败
    ↓
DRM connector 状态 = unknown / disabled
    ↓
无 framebuffer 设备 (/dev/fb0)
    ↓
无画面输出
```

### 关键诊断命令与输出

1. **DRM connector 状态**：
   ```
   /sys/class/drm/card0-HDMI-A-1/status → unknown
   /sys/class/drm/card0-HDMI-A-1/enabled → disabled
   ```

2. **I2C 设备检测** — SiI9022 芯片在 bus 7 地址 0x3b 被正确识别 (`UU`)：
   ```
   $ sudo i2cdetect -y -r 7
        0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
   00:                         -- -- -- -- -- -- -- --
   10: -- -- -- -- -- -- -- -- UU -- -- -- -- -- -- --
   30: -- -- -- -- -- -- -- -- -- -- -- UU -- -- -- --
   ```

3. **modetest 列出可用分辨率** — EDID 读取正常（通过强制 connected 触发）：
   ```
   #0 1024x600 60.04Hz (preferred)
   #1 1920x1080 60.00Hz
   #2 1600x900  60.00Hz
   #3 1360x768  59.95Hz
   #4 1280x720  60.00Hz
   ```

4. **CRTC 选择错误** — CRTC 63 (bt1120) 是摄像头直出通道，不能用于 HDMI：
   ```
   $ sudo modetest -M vs-drm -s 74@63:1024x600
   failed to set mode: Invalid argument
   ```
   正确应使用 **CRTC 31 (dc8000)** 显示控制器。

5. **vs_drm 驱动无 fbdev 接口** — 即使启用了 `DRM_FBDEV_EMULATION=y`，该驱动不创建 `/dev/fb0` 设备。

---

## 解决方案

### 临时方案（手动启用，重启失效）

```bash
# 1. 强制标记 HDMI 已连接
echo "connected" | sudo tee /sys/class/drm/card0-HDMI-A-1/status

# 2. 用 modetest 设置显示模式（使用 CRTC 31）
sudo modetest -M vs-drm -s 74@31:1024x600 > /dev/null 2>&1 &

# 3. 启动 weston 桌面
sudo XDG_RUNTIME_DIR=/tmp/run weston --tty=1 --backend=drm-backend.so &
```

### 持久化方案（开机自动启用）

#### 步骤 1：创建 HDMI 初始化脚本

```bash
sudo tee /usr/local/bin/init-hdmi.sh << 'EOF'
#!/bin/bash
# 等待 DRM 初始化完成
for i in $(seq 1 30); do
    if [ -e /sys/class/drm/card0-HDMI-A-1/status ]; then
        break
    fi
    sleep 1
done

# 强制标记 HDMI 已连接
echo "connected" > /sys/class/drm/card0-HDMI-A-1/status 2>/dev/null
sleep 1

# 用 CRTC 31 (dc8000) 设置显示模式
modetest -M vs-drm -s 74@31:1024x600 > /dev/null 2>&1 &

echo "HDMI initialized"
EOF

sudo chmod +x /usr/local/bin/init-hdmi.sh
```

#### 步骤 2：创建 systemd 服务

```bash
sudo tee /etc/systemd/system/init-hdmi.service << 'EOF'
[Unit]
Description=Initialize HDMI display
After=multi-user.target
Wants=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/init-hdmi.sh
RemainAfterExit=yes
User=root

[Install]
WantedBy=multi-user.target
EOF
```

#### 步骤 3：启用服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable init-hdmi.service
```

#### 步骤 4：创建 Weston 自动启动服务

```bash
sudo tee /etc/systemd/system/weston.service << 'EOF'
[Unit]
Description=Weston Wayland compositor
After=init-hdmi.service
Requires=init-hdmi.service

[Service]
Type=simple
Environment=XDG_RUNTIME_DIR=/tmp/run
ExecStartPre=/bin/mkdir -p /tmp/run
ExecStartPre=/bin/chmod 700 /tmp/run
ExecStart=/usr/bin/weston --tty=1 --backend=drm-backend.so
Restart=on-failure
User=root

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable weston.service
```

---

## USB 触摸屏配置

### 触摸屏信息

该显示器为 **QDtech MPI7003** 多点触摸屏，通过 USB 连接到 RDK X5 主板。

| 项目 | 详情 |
|------|------|
| 设备名称 | QDtech MPI7003 |
| USB ID | 0483:5750 (STMicroelectronics) |
| 驱动 | `hid-multitouch`（内核原生） |
| 输入设备 | `/dev/input/event1` |
| libinput 属性 | `ID_INPUT_TOUCHSCREEN=1` |

### 即插即用

内核 `hid-multitouch` 驱动在 USB 插入时自动加载，无需任何手动配置。通过以下命令验证：

```bash
# 查看触摸设备
ls -la /dev/input/by-id/usb-QDtech_MPI7003*

# 实时监控触摸事件（触摸屏幕看坐标输出）
sudo evtest /dev/input/event1

# 查看 libinput 设备信息
sudo libinput list-devices 2>/dev/null | grep -A20 MPI7003
```

> **注意**：`evtest` 需单独安装：`sudo apt install evtest -y`

### 在 Weston 中使用触摸

启动 weston 时无需额外参数，weston 通过 libinput 自动识别触摸屏：

```bash
sudo XDG_RUNTIME_DIR=/tmp/run weston --tty=1 --backend=drm-backend.so &
```

如果需要禁用触摸（只当显示器用）：

```bash
# 临时禁用
sudo evtest --grab /dev/input/event1 > /dev/null &

# 或者卸载 hid-multitouch 驱动
sudo modprobe -r hid-multitouch
```

### 触摸校准

`hid-multitouch` 设备通常会用 EDID 报告的屏幕尺寸自动匹配触摸坐标，一般无需手动校准。如遇触摸偏移：

```bash
# 安装校准工具
sudo apt install xinput-calibrator -y 2>/dev/null

# 查看 libinput 校准矩阵属性
sudo libinput list-devices 2>/dev/null | grep -A30 MPI7003
```

---

## 诊断工具速查

| 命令 | 用途 |
|------|------|
| `cat /sys/class/drm/card0-HDMI-A-1/status` | 查看 HDMI 连接状态 |
| `cat /sys/class/drm/card0-HDMI-A-1/enabled` | 查看 HDMI 是否启用 |
| `sudo modetest -M vs-drm` | 列出所有 DRM 资源 (CRTC/Plane/Connector/Mode) |
| `sudo modetest -M vs-drm -s 74@31:1024x600` | 设置显示模式 |
| `sudo i2cdetect -y -r 7` | 检测 I2C bus 7 上的设备 |
| `lsmod \| grep sii902x` | 检查 HDMI 芯片驱动是否加载 |
| `dmesg \| grep -iE "sii902\|hdmi\|drm"` | 查看驱动初始化日志 |
| `sudo cat /sys/kernel/debug/dri/0/state` | 查看完整 DRM 状态（需挂载 debugfs） |
| `ps aux \| grep weston` | 检查 weston 是否在运行 |
| `lsusb` | 查看 USB 设备列表 |
| `ls -la /dev/input/by-id/` | 查看输入设备（含触摸屏） |
| `sudo evtest /dev/input/event1` | 实时监控触摸事件 |
| `sudo libinput list-devices` | 查看 libinput 设备详细信息 |

### 挂载 debugfs

```bash
sudo mount -t debugfs none /sys/kernel/debug
```

---

## CRTC 对照表

| CRTC ID | 名称 | 用途 |
|---------|------|------|
| **31** | dc8000 | 显示控制器，用于 HDMI / DSI 输出 |
| 63 | bt1120 | 摄像头直出通道，不可用于 HDMI |

> 设置模式时必须使用 CRTC 31，否则报 `Invalid argument`。

---

## 支持的 HDMI 分辨率

| 分辨率 | 刷新率 | 类型 |
|--------|--------|------|
| 1024x600 | 60.04Hz | preferred（显示器首选） |
| 1920x1080 | 60.00Hz | driver |
| 1600x900 | 60.00Hz | driver |
| 1360x768 | 59.95Hz | — |
| 1280x720 | 60.00Hz | driver |

修改 `/usr/local/bin/init-hdmi.sh` 中的分辨率参数即可切换。

---

## 注意事项

1. **HDMI 和 MIPI DSI 不能同时使用**，系统默认 HDMI 输出。
2. `srpi-config` (`Display Options → D1 Dsiplay Choice → HDMI`) 和手动切换 X11 配置文件的方法对 Ubuntu Server 无效，因为 Server 版不使用 X11。
3. Ubuntu Server 默认无桌面环境，需安装 weston 等 Wayland 合成器来渲染图形界面。
4. `vs-drm` 驱动不创建 `/dev/fb0` 设备，这是预期行为，不影响 HDMI 输出。
5. 如果显示器支持不同分辨率，修改 `modetest -s 74@31:分辨率` 参数即可。

---

## 参考

- [RDK X5 官方显示屏使用文档](https://d-robotics.github.io/rdk_doc/Quick_start/display_use/display_rdkx5)
- [地瓜机器人社区](https://d-robotics.cc/)
