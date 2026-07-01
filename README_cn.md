# LibraryMaster — 图书馆智能助手与自主导航小车系统

**LibraryMaster** 是一个集成系统，结合了**智能图书馆图书检索助手**与**自主机器人导航**功能。用户可通过触摸屏一体机上的语音/文字搜索图书馆藏书，同时机器人能够自主导航到图书的实体位置。

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PC 端 (x86)                                 │
│                                                                     │
│  ┌─ Embedding ─────────────┐    ┌─ RAG ──────────────────────────┐ │
│  │ SGLang 嵌入服务         │    │ LanceDB + FastAPI               │ │
│  │ Qwen3-Embedding-0.6B   │◄──►│ 向量/关键词检索                  │ │
│  │ 端口 30000              │    │ 端口 9014 (Docker)              │ │
│  └─────────────────────────┘    └──────────┬──────────────────────┘ │
│                                            │                        │
│  ┌─ mycar_pc ───────────────────────────┐  │                        │
│  │  slam_toolbox (2D 分布式建图)         │  │                        │
│  │  RTAB-Map (3D RGB-D 建图)            │  │                        │
│  │  RViz2 可视化                        │  │                        │
│  └──────────────────────────────────────┘  │                        │
└──────────────────┬──────────────────────────┘                        │
                   │ ROS2 DDS (Fast-DDS, UDP, ROS_DOMAIN_ID=42)       │
                   │ OpenVPN                                         │
┌──────────────────┴──────────────────────────────────────────────────┐
│                      小车端 (RDK X5)                                 │
│                                                                     │
│  ┌─ mycar ──────────────────────────────────────────────────────┐  │
│  │  驱动 (串口→MCU) + 里程计 + EKF + 双目相机                    │  │
│  │  slam_toolbox (本地 2D) / RTAB-Map (本地 3D)                │  │
│  │  Nav2 自主导航 + 航点导航 + REST API                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─ voice_agent ────────────────────────────────────────────────┐  │
│  │  Agent 服务器 (FastAPI, 端口 9015 Docker)                    │  │
│  │  │─ DeepSeek API + Function Calling Agent                    │  │
│  │  │─ Web 界面 (HDMI 触摸屏 Kiosk)                            │  │
│  │  │─ 语音中继 (录音 → 讯飞 ASR)                              │  │
│  │  │─ 语音唤醒 KWS ("你好小图")                                │  │
│  │  │─ 讯飞 TTS (语音输出)                                     │  │
│  │  └── RAG API (PC :9014) 图书检索                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 模块分布

| 模块 | 平台 | 说明 |
|------|------|------|
| `voice_agent/` | 小车端 (RDK X5) | 语音/Web/CLI 交互式图书查询智能体，基于 DeepSeek |
| `rag/` | PC 端 (x86) | RAG 向量检索服务：LanceDB + FastAPI (Docker) |
| `Embedding/` | PC 端 (x86) | SGLang 嵌入服务 (Qwen3-Embedding-0.6B) |
| `mycar/` | 小车端 (RDK X5) | 小车嵌入式 ROS2 工作空间 (驱动、SLAM、Nav2) |
| `mycar_pc/` | PC 端 (x86) | PC 端分布式建图 (slam_toolbox、RTAB-Map、RViz2) |
| `map/`, `maps/` | — | 已保存的地图和航点文件 |

---

## 功能特性

### 📚 图书馆图书检索 (voice_agent + rag + embedding)
- **语音交互**：通过触摸屏一体机或唤醒词"你好小图"自然语音交流
- **文字交互**：通过触摸屏虚拟键盘或 CLI 输入查询
- **语义搜索**：自然语言查询 → 向量嵌入 → LanceDB 相似度检索
- **关键词搜索**：按书名模糊匹配
- **AI 智能体**：DeepSeek API + Function Calling，智能对话式检索

### 🤖 自主小车导航 (mycar + mycar_pc)
- **2D 分布式建图**：小车端传感器管线，PC 端运行 slam_toolbox
- **3D 建图**：基于双目深度相机的 RTAB-Map RGB-D 建图
- **自主导航**：Nav2 导航栈 (AMCL + SmacPlanner + Pure Pursuit)
- **航点导航**：保存/加载命名航点，通过 REST API 控制导航
- **里程计标定**：自动化里程计标定与验证工具
- **数据诊断**：全面的话题/TF 树/ROS 节点诊断工具

---

## 环境要求

### 硬件
| 组件 | 规格 |
|------|------|
| RDK X5 | 小车端主控，Ubuntu Server 22.04 |
| Yahboom Rosmaster | 四驱差速驱动板，串口 (USB) |
| 双目相机 | MIPI 接口，1280*1080@120fps |
| HDMI 触摸屏 | 1024×600 (如 QDtech MPI7002/7003) |
| PC | x86，推荐 NVIDIA GPU（3D 建图） |

### 软件
- **小车端 (RDK X5)**：TROS Humble (ROS2)、Docker + docker-compose、Python 3.10+
- **PC 端**：ROS2 Humble (Ubuntu 22.04)、Docker + docker-compose、Python 3.10+、NVIDIA 驱动
- **网络**：OpenVPN（跨机器 ROS2 DDS 通信），`ROS_DOMAIN_ID=42`

---

## 部署流程

### 第一阶段：环境安装

#### 1.1 小车端 (RDK X5)

```bash
# TROS Humble 环境（RDK X5 官方系统已预装）
source /opt/tros/humble/setup.bash

# 安装 Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# 安装 voice_agent Python 依赖
cd ~/LibraryMaster/voice_agent
pip install -r app/requirements.txt
pip install -r src/requirements-host.txt

# HDMI 显示设置（详见 docs/rdk_x5_hdmi_display_setup.md）
echo "connected" | sudo tee /sys/class/drm/card0-HDMI-A-1/status
sudo modetest -M vs-drm -s 74@31:1024x600 > /dev/null 2>&1 &
sudo XDG_RUNTIME_DIR=/tmp/run weston --tty=1 --backend=drm-backend.so &

# 配置环境变量
cd ~/LibraryMaster/voice_agent
cp .env.example .env
# 编辑 .env：设置 DEEPSEEK_API_KEY、XUNFEI_ASR_APP_ID、XUNFEI_ASR_API_KEY 等

# 编译 mycar 工作空间
cd ~/LibraryMaster/mycar
./build.sh
```

#### 1.2 PC 端 (x86)

```bash
# 安装 ROS2 Humble
# https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debians.html

# 安装 Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# 安装 Python 依赖
pip install openai lancedb fastapi uvicorn pandas pydantic

# 编译 mycar_pc 工作空间
cd ~/LibraryMaster/mycar_pc
./build.sh

# 配置 OpenVPN（确保小车和 PC 在同一网络）
# 两端都设置 ROS_DOMAIN_ID=42
# 配置 Fast-DDS 禁用共享内存 (config/fastdds.xml)
```

### 第二阶段：数据处理（PC 端）

#### 2.1 启动嵌入服务

```bash
cd ~/LibraryMaster/Embedding
# 从 HuggingFace 下载模型到 ~/model/Qwen3_embedding-0.6b
./start_embedding.sh
```

#### 2.2 导入图书数据到 LanceDB

准备包含图书数据的 CSV 文件 `out.csv`（需包含 1024 维的 `embedding` 向量列）。

```bash
cd ~/LibraryMaster/rag
python3 src/input.py
```

#### 2.3 启动 RAG API 服务

```bash
cd ~/LibraryMaster/rag
docker compose up -d --build
# 验证：curl http://localhost:9014/
```

### 第三阶段：标定与 2D 分布式建图

#### 3.1 里程计标定（小车端）

```bash
cd ~/LibraryMaster/mycar
./calibrate_odom.sh                # 手动遥控小车完成标定
./verify_odom.sh                   # 验证标定精度
# 或一键完成：./calibrate_and_verify.sh
```

#### 3.2 2D 分布式建图

**步骤 1**：启动小车端传感器管线（向 PC 发送数据）

```bash
cd ~/LibraryMaster/mycar
./start_mycar.sh mapping_distributed /dev/ttyUSB0
```

**步骤 2**：启动 PC 端 SLAM + RViz2

```bash
cd ~/LibraryMaster/mycar_pc
./start_pc.sh mapping2d
```

**步骤 3**：遥控小车遍历图书馆

```
键盘遥控：
  i = 前进
  , = 后退
  j = 左转
  l = 右转
  k = 停止
```

**步骤 4**：建图完成后保存地图

```bash
# 在 PC 端新终端执行
ros2 run nav2_map_server map_saver_cli -f ~/LibraryMaster/map/mycar_map
```

地图将保存为 `mycar_map.pgm` 和 `mycar_map.yaml`。

### 第四阶段：标定航点

保存地图后，启动导航模式来标记航点。

```bash
# 小车端 - 启动带航点支持的导航
cd ~/LibraryMaster/mycar
./start_mycar.sh waypoint_navigation /dev/ttyUSB0

# PC 端 - 启动监控
cd ~/LibraryMaster/mycar_pc
./start_pc.sh nav_monitor
```

**在 RViz2 中标记航点：**
1. 使用 **2D Pose Estimate** 在地图上标定小车初始位置
2. 等待 AMCL 粒子收敛
3. 在终端设置航点名：`./scripts/save_waypoint.sh "书架A"`
4. 或使用 RViz 的 **Publish Point** 按钮：
   ```bash
   ros2 topic pub /set_waypoint_name std_msgs/String "data: '出入口'" --once
   # 然后在 RViz 中用 Publish Point 点击地图位置
   ```
5. 航点自动保存到 `mycar_map_waypoints.yaml`

### 第五阶段：实际运行

#### 5.1 启动所有服务

**PC 端：**
```bash
# 1. 启动嵌入服务（如未运行）
cd ~/LibraryMaster/Embedding
./start_embedding.sh

# 2. 启动 RAG API
cd ~/LibraryMaster/rag
docker compose up -d
```

**小车端 (RDK X5)：**
```bash
# 1. 启动语音助手（Docker + Web UI + 语音服务）
cd ~/LibraryMaster/voice_agent

# 完整服务：Docker + Kiosk + KWS + 语音中继
./start_voice_agent.sh --kws

# 带 HDMI Kiosk 显示
./start_voice_agent.sh --kiosk

# 或分别启动：
./start_voice_agent.sh                    # 仅 Docker (Agent Server)
# 另一个终端：
python3 src/voice_relay.py                # 语音中继（麦克风录音）
python3 src/kws_service.py                # 唤醒词检测

# 2. 启动小车导航
cd ~/LibraryMaster/mycar
./start_mycar.sh waypoint_navigation /dev/ttyUSB0
```

**PC 端（监控）：**
```bash
cd ~/LibraryMaster/mycar_pc
./start_pc.sh nav_monitor
```

#### 5.2 交互方式

**语音模式（触摸屏一体机）：**
- 说 **"你好小图"** 唤醒系统
- 自然语音提问，如"帮我找一下人工智能的书"
- Agent 通过 RAG API 检索并在屏幕上展示结果
- 说 **"导航到书架A"** 命令小车导航

**文字模式（CLI）：**
```bash
cd ~/LibraryMaster/voice_agent
python3 main.py
>>> 帮我找一下深度学习相关的书
```

**REST API（程序调用）：**
```bash
# 导航到指定坐标
curl -X POST http://<小车IP>:5000/navigate \
  -H "Content-Type: application/json" \
  -d '{"x": 1.5, "y": 2.0, "yaw": 0.0}'

# 查询小车状态
curl http://<小车IP>:5000/status

# 取消导航
curl -X POST http://<小车IP>:5000/cancel
```

---

## 模块说明

### voice_agent/ — 语音助手（小车端）

| 文件 | 说明 |
|------|------|
| `main.py` | CLI 入口 |
| `config.py` | 全局配置（API 密钥、端口、提示词） |
| `kiosk.py` | 全屏 WebKit2GTK Kiosk 浏览器 (Weston Wayland) |
| `app/agent_server.py` | FastAPI + WebSocket 服务器 (端口 9015) |
| `app/agent.py` | ReAct Agent 主循环 (DeepSeek Function Calling) |
| `app/llm.py` | DeepSeek LLM 封装（支持流式输出） |
| `app/tools.py` | 工具定义：search_books、get_library_info |
| `app/static/` | Web UI 前端 (SPA) |
| `src/voice_relay.py` | HTTP 录音中继服务 (端口 9016) |
| `src/kws_service.py` | 关键词唤醒服务 ("你好小图") |
| `src/xunfei_asr.py` | 讯飞流式语音识别客户端 |
| `src/xunfei_tts.py` | 讯飞流式语音合成客户端 |
| `docker-compose.yml` | Agent Server Docker 编排 |

### rag/ — RAG 向量检索服务（PC 端）

| 文件 | 说明 |
|------|------|
| `docker-compose.yml` | LanceDB + FastAPI Docker 编排 |
| `dockerfile` | Docker 镜像构建 |
| `src/input.py` | 从 CSV 导入图书数据到 LanceDB |
| `src/vector_query.py` | 文本向量化 + LanceDB 检索 |
| `src/rag_api.py` | FastAPI 端点 (/search、/keyword_search、/query) |
| `src/main.py` | 服务入口 |

### Embedding/ — 嵌入服务（PC 端）

| 文件 | 说明 |
|------|------|
| `start_embedding.sh` | 启动 SGLang 嵌入服务器 |
| `model/` | Qwen3-Embedding-0.6B 模型文件 |
| `test/` | 嵌入 API 测试脚本 |

### mycar/ — 小车 ROS2 工作空间（小车端）

| 目录/文件 | 说明 |
|-----------|------|
| `src/mycar_driver/` | 驱动、里程计、EKF、相机、LaserScan 节点 |
| `src/mycar_f/` | URDF 机器人模型 (SolidWorks → STL) |
| `src/mycar_slam/` | 本地 2D slam_toolbox 建图 |
| `src/mycar_rtabmap/` | 本地 3D RTAB-Map 建图 |
| `src/mycar_navigation/` | Nav2 导航、航点保存、地图保活 |
| `scripts/` | save_waypoint.sh、goto.sh |
| `config/` | Fast-DDS 配置、Nav2 参数 |
| `calibrate_odom.sh` | 里程计标定 |
| `verify_odom.sh` | 里程计验证 |
| `calibrate_and_verify.sh` | 一键标定+验证 |
| `diagnose.sh` | 数据链路诊断 |
| `start_mycar.sh` | 统一启动入口（所有模式） |

### mycar_pc/ — PC 端分布式建图

| 目录/文件 | 说明 |
|-----------|------|
| `src/mycar_rtabmap/` | PC 端 SLAM 启动文件、配置、RViz 布局 |
| `src/mycar_f/` | URDF 模型副本 (robot_state_publisher 用) |
| `test_3d_mapping.py` | 3D 建图数据流测试工具 |
| `test_3d_mapping.sh` | 一键测试脚本 |
| `start_pc.sh` | 统一启动入口 (scan_view、mapping2d、mapping3d_rgbd、nav_monitor) |

---

## 快速命令参考

### 小车端 (RDK X5)

| 操作 | 命令 |
|------|------|
| 编译工作空间 | `./build.sh` |
| 里程计标定 | `./calibrate_odom.sh` |
| 2D 分布式建图（小车） | `./start_mycar.sh mapping_distributed` |
| 导航+航点 | `./start_mycar.sh waypoint_navigation` |
| 启动语音助手 | `cd ../voice_agent && ./start_voice_agent.sh` |
| 语音+KWS | `cd ../voice_agent && ./start_voice_agent.sh --kws` |
| 语音+Kiosk | `cd ../voice_agent && ./start_voice_agent.sh --kiosk` |
| 仅语音中继 | `cd ../voice_agent && python3 src/voice_relay.py` |
| 仅 KWS | `cd ../voice_agent && python3 src/kws_service.py` |
| 诊断数据 | `./diagnose.sh` |
| 保存航点 | `./scripts/save_waypoint.sh "航点名"` |
| 导航到航点 | `./scripts/goto.sh "航点名"` |
| 保存地图 | `ros2 run nav2_map_server map_saver_cli -f ~/LibraryMaster/map/mycar_map` |

### PC 端 (x86)

| 操作 | 命令 |
|------|------|
| 编译工作空间 | `./build.sh` |
| 启动嵌入服务 | `cd ../Embedding && ./start_embedding.sh` |
| 导入图书数据 | `cd ../rag && python3 src/input.py` |
| 启动 RAG API | `cd ../rag && docker compose up -d` |
| 2D 分布式建图（PC） | `./start_pc.sh mapping2d` |
| 导航监控 | `./start_pc.sh nav_monitor` |
| 数据流测试 | `./test_3d_mapping.sh` |

---

## License

MIT
