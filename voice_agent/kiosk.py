#!/usr/bin/env python3
"""
kiosk.py — 极简 Kiosk 浏览器

在 Weston Wayland 上全屏渲染 Web UI，无需桌面环境。
依赖: python3-gi, gir1.2-webkit2-4.0, gir1.2-gtk-3.0

用法:
  ./kiosk.py                               # 默认 http://localhost:9015
  ./kiosk.py http://192.168.1.100:9015     # 指定 URL
  ./kiosk.py --touch                       # 启用触摸调试（点击显示坐标）

注意: 必须在 RDK X5 本地终端 (TTY1) 上运行，Weston 需提前启动。
      不能通过 SSH 运行（SSH 没有 Wayland 显示环境）。
"""

import sys
import os
import signal

# ── 强制 Wayland 环境（必须在 import GTK 之前设置） ──
os.environ["GDK_BACKEND"] = "wayland"
os.environ.setdefault("XDG_RUNTIME_DIR", "/tmp/run")

# RDK X5 vs-drm GPU 驱动缺失时使用软件渲染
# 注: 不设置 LIBGL_ALWAYS_SOFTWARE，让 Mesa 优先尝试硬件加速
# 如果 vs-drm DRI 驱动安装了会自动使用；否则回退 llvmpipe
os.environ.setdefault("WEBKIT_DISABLE_COMPOSITING_MODE", "1")
# 禁用 WebKit 沙箱（容器/嵌入式环境不需要）
os.environ["WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS"] = "1"

# ── 检查 Wayland socket ──────────────────────────────
WAYLAND_SOCKET = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR", "/tmp/run"), "wayland-0"
)


def check_wayland():
    """检查 Wayland 显示环境是否可用"""
    import subprocess
    # 用 ls 命令检查（避免权限问题）
    try:
        result = subprocess.run(
            ["sudo", "ls", "-la", WAYLAND_SOCKET],
            capture_output=True, timeout=2,
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass
    # 也检查常见的备选路径
    for alt in ["/run/wayland-0", "/tmp/wayland-0"]:
        if os.path.exists(alt):
            os.environ["WAYLAND_DISPLAY"] = os.path.basename(alt)
            return True
    return False


def print_wayland_help():
    print("❌ 未检测到 Wayland 显示环境 (Weston)！")
    print()
    print("Kiosk 浏览器需要在 RDK X5 的 HDMI 显示器上运行。")
    print("请先在 RDK X5 本地终端执行：")
    print()
    print("  # 1. 确保 HDMI 已启用")
    print('  echo "connected" | sudo tee /sys/class/drm/card0-HDMI-A-1/status')
    print("  sudo modetest -M vs-drm -s 74@31:1024x600 > /dev/null 2>&1 &")
    print()
    print("  # 2. 启动 Weston")
    print("  sudo XDG_RUNTIME_DIR=/tmp/run weston --tty=1 --backend=drm-backend.so &")
    print()
    print("  # 3. 在 Weston 终端中运行 kiosk")
    print("  ./kiosk.py")
    print()
    print("或者使用 SSH 启动后，切到 TTY1 (Ctrl+Alt+F1) 查看显示效果。")
    sys.exit(1)


if not check_wayland():
    print_wayland_help()

# ── 导入 GTK / WebKit ────────────────────────────────
try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.0")
    from gi.repository import Gtk, WebKit2, GLib
except ImportError as e:
    print(f"❌ 缺少依赖: {e}")
    print("   sudo apt install -y python3-gi gir1.2-webkit2-4.0 gir1.2-gtk-3.0")
    sys.exit(1)


class KioskWindow:
    def __init__(self, url: str, touch_mode: bool = False):
        self.url = url
        self.touch_mode = touch_mode
        self.load_ok = False

        # 使用 Gtk.init_check() 优雅处理初始化失败
        if not Gtk.init_check()[0]:
            print("❌ GTK 初始化失败 — Wayland 显示环境不可用。")
            print_wayland_help()

        # 创建全屏窗口
        self.win = Gtk.Window(title="LibraryMaster")
        self.win.set_default_size(1024, 600)
        self.win.connect("destroy", Gtk.main_quit)
        self.win.connect("key-press-event", self._on_key)

        # WebView — 设置必须在 load_uri 之前完成
        self.webview = WebKit2.WebView()

        # 启用开发者工具（方便调试）
        settings = self.webview.get_settings()
        settings.set_enable_javascript(True)
        settings.set_enable_html5_local_storage(True)
        settings.set_enable_smooth_scrolling(True)
        settings.set_enable_developer_extras(True)
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_allow_universal_access_from_file_urls(False)
        self.webview.set_settings(settings)

        # 信号连接（兼容 WebKit2GTK 2.50 / 4.0）
        self.webview.connect("load-changed", self._on_load_changed)

        # 加载页面
        print(f"🌐 正在加载: {url}")
        self.webview.load_uri(url)

        # 放入窗口 — 先显示再全屏，确保 Weston 正确响应
        self.win.add(self.webview)
        self.win.set_decorated(False)  # 无边框
        # 先设置大小再全屏，双重保险
        self.win.set_default_size(1024, 600)
        self.win.set_resizable(False)

        # 触摸调试
        if touch_mode:
            self.webview.connect("button-press-event", self._on_touch)

        # 安全退出 (Ctrl+C)
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        # 5 秒后检查页面状态
        GLib.timeout_add_seconds(5, self._check_loaded)

    def _on_load_changed(self, webview, event):
        if event == WebKit2.LoadEvent.FINISHED:
            self.load_ok = True
            uri = webview.get_uri()
            title = webview.get_title() or ""
            print(f"✅ 页面加载完成: {uri}")
            print(f"📄 标题: {title}")
        elif event == WebKit2.LoadEvent.STARTED:
            print(f"🔄 开始加载...")
        elif event == WebKit2.LoadEvent.COMMITTED:
            pass

    def _check_loaded(self):
        """5 秒后检查页面是否加载完成"""
        if not self.load_ok:
            print(f"⚠️ 页面可能未完全加载，正在重试...")
            # 尝试重新加载
            self.webview.reload()
        return False  # 只运行一次

    def _on_key(self, win, event):
        """键盘快捷键"""
        key_name = event.get_keyval()[1]
        if key_name == 'q' and (event.state & 4):  # Ctrl+Q
            Gtk.main_quit()
        elif key_name == 'r' and (event.state & 4):  # Ctrl+R 刷新
            self.webview.reload()
            print("🔄 刷新页面")
        return False

    def _on_touch(self, widget, event):
        print(f"🖱️ 点击: ({event.x:.0f}, {event.y:.0f})")
        return False

    def run(self):
        self.win.show_all()
        # 显示后再全屏 — Weston 需要窗口可见后才能正确全屏
        self.win.fullscreen()
        print(f"🌐 Kiosk 浏览器已启动")
        print(f"   Ctrl+R 刷新 | Ctrl+Q 退出")
        Gtk.main()


def main():
    args = sys.argv[1:]

    url = "http://localhost:9015"
    touch_mode = False

    # 解析参数
    filtered = []
    for a in args:
        if a == "--touch":
            touch_mode = True
        elif a.startswith("http://") or a.startswith("https://"):
            url = a
        else:
            filtered.append(a)

    KioskWindow(url=url, touch_mode=touch_mode).run()


if __name__ == "__main__":
    main()
