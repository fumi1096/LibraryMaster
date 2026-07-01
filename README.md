# LibraryMaster — Library Smart Assistant & Autonomous Robot Navigation System

**LibraryMaster** is an integrated system that combines an **intelligent library book search assistant** with **autonomous robot navigation**. It enables users to search for library books via voice/text on a touchscreen kiosk, while the robot can autonomously navigate to the physical book locations in the library.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PC Side (x86)                                │
│                                                                     │
│  ┌─ Embedding ─────────────┐    ┌─ RAG ──────────────────────────┐ │
│  │ SGLang Service          │    │ LanceDB + FastAPI               │ │
│  │ Qwen3-Embedding-0.6B   │◄──►│ Vector/Keyword Search           │ │
│  │ Port 30000              │    │ Port 9014 (Docker)              │ │
│  └─────────────────────────┘    └──────────┬──────────────────────┘ │
│                                            │                        │
│  ┌─ mycar_pc ───────────────────────────┐  │                        │
│  │  slam_toolbox (2D Distributed SLAM)  │  │                        │
│  │  RTAB-Map (3D RGB-D SLAM)           │  │                        │
│  │  RViz2 Visualization                │  │                        │
│  └──────────────────────────────────────┘  │                        │
└──────────────────┬──────────────────────────┘                        │
                   │ ROS2 DDS (Fast-DDS, UDP, ROS_DOMAIN_ID=42)       │
                   │ OpenVPN                                         │
┌──────────────────┴──────────────────────────────────────────────────┐
│                      Car Side (RDK X5)                              │
│                                                                     │
│  ┌─ mycar ──────────────────────────────────────────────────────┐  │
│  │  Driver (Serial → MCU) + Odom + EKF + Binocular Camera       │  │
│  │  slam_toolbox (Local 2D) / RTAB-Map (Local 3D)              │  │
│  │  Nav2 Autonomous Navigation + Waypoint Navigation + REST API │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─ voice_agent ────────────────────────────────────────────────┐  │
│  │  Agent Server (FastAPI, Port 9015 Docker)                    │  │
│  │  │─ DeepSeek API + Function Calling Agent                    │  │
│  │  │─ Web UI (Touchscreen Kiosk on HDMI)                      │  │
│  │  │─ Voice Relay (Recording → iFlytek ASR)                   │  │
│  │  │─ KWS Wake-up ("你好小图")                                 │  │
│  │  │─ iFlytek TTS (Voice Output)                              │  │
│  │  └── RAG API (PC :9014) for book search                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Module Breakdown

| Module | Platform | Description |
|--------|----------|-------------|
| `voice_agent/` | Car (RDK X5) | Voice/Web/CLI interactive book search agent, DeepSeek-based |
| `rag/` | PC (x86) | RAG vector search service: LanceDB + FastAPI (Docker) |
| `Embedding/` | PC (x86) | SGLang embedding service (Qwen3-Embedding-0.6B) |
| `mycar/` | Car (RDK X5) | Robot car embedded ROS2 workspace (driver, SLAM, Nav2) |
| `mycar_pc/` | PC (x86) | PC-side distributed mapping (slam_toolbox, RTAB-Map, RViz2) |
| `map/`, `maps/` | — | Saved maps and waypoints |

---

## Features

### 📚 Library Book Search (voice_agent + rag + embedding)
- **Voice Interaction**: Speak naturally via touchscreen kiosk or wake word "你好小图"
- **Text Interaction**: Type queries via virtual keyboard on touchscreen or CLI
- **Semantic Search**: Natural language query → vector embedding → LanceDB similarity search
- **Keyword Search**: Fuzzy match by book title
- **AI Agent**: DeepSeek API with Function Calling for intelligent conversational search

### 🤖 Autonomous Robot Navigation (mycar + mycar_pc)
- **2D Distributed Mapping**: slam_toolbox on PC, sensor pipeline on car (RDK X5)
- **3D Mapping**: RTAB-Map RGB-D with binocular depth camera
- **Autonomous Navigation**: Nav2 stack (AMCL + SmacPlanner + Pure Pursuit)
- **Waypoint Navigation**: Save/load named waypoints, navigate via REST API
- **Odom Calibration**: Automated odometry calibration and verification tools
- **Data Diagnostics**: Comprehensive topic/TF tree/ROS node diagnostics

---

## Prerequisites

### Hardware
| Component | Specification |
|-----------|---------------|
| RDK X5 | Car-side main controller, Ubuntu Server 22.04 |
| Yahboom Rosmaster | 4-wheel differential drive board, serial (USB) |
| Stereo Camera | MIPI binocular, 640×352@30fps |
| HDMI Touchscreen | 1024×600 (e.g., QDtech MPI7002/7003) |
| PC | x86 with NVIDIA GPU (recommended for 3D mapping) |

### Software
- **Car (RDK X5)**: TROS Humble (ROS2), Docker + docker-compose, Python 3.10+
- **PC**: ROS2 Humble (Ubuntu 22.04), Docker + docker-compose, Python 3.10+, NVIDIA drivers
- **Network**: OpenVPN (cross-machine ROS2 DDS), `ROS_DOMAIN_ID=42`

---

## Deployment Guide

### Phase 1: Environment Setup

#### 1.1 Car Side (RDK X5)

```bash
# Install TROS Humble (pre-installed on RDK X5 official system)
source /opt/tros/humble/setup.bash

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# Install Python dependencies for voice_agent
cd ~/LibraryMaster/voice_agent
pip install -r app/requirements.txt
pip install -r src/requirements-host.txt

# HDMI display setup (see docs/rdk_x5_hdmi_display_setup.md for details)
echo "connected" | sudo tee /sys/class/drm/card0-HDMI-A-1/status
sudo modetest -M vs-drm -s 74@31:1024x600 > /dev/null 2>&1 &
sudo XDG_RUNTIME_DIR=/tmp/run weston --tty=1 --backend=drm-backend.so &

# Configure environment
cd ~/LibraryMaster/voice_agent
cp .env.example .env
# Edit .env: set DEEPSEEK_API_KEY, XUNFEI_ASR_APP_ID, XUNFEI_ASR_API_KEY, etc.

# Build mycar workspace
cd ~/LibraryMaster/mycar
./build.sh
```

#### 1.2 PC Side (x86)

```bash
# Install ROS2 Humble
# https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debians.html

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# Install Python dependencies
pip install openai lancedb fastapi uvicorn pandas pydantic

# Build mycar_pc workspace
cd ~/LibraryMaster/mycar_pc
./build.sh

# Set up OpenVPN (ensure car and PC are on the same network)
# Configure ROS_DOMAIN_ID=42 in both car and PC
# Configure Fast-DDS to disable SHM (config/fastdds.xml)
```

### Phase 2: Data Processing (PC Side)

#### 2.1 Start Embedding Service

```bash
cd ~/LibraryMaster/Embedding
# Download model from HuggingFace to ~/model/Qwen3_embedding-0.6b
./start_embedding.sh
```

#### 2.2 Import Book Data to LanceDB

Prepare a CSV file `out.csv` with book data (including `embedding` column with 1024-dim vectors).

```bash
cd ~/LibraryMaster/rag
python3 src/input.py
```

#### 2.3 Start RAG API Service

```bash
cd ~/LibraryMaster/rag
docker compose up -d --build
# Verify: curl http://localhost:9014/
```

### Phase 3: Calibration & 2D Distributed Mapping

#### 3.1 Odometry Calibration (Car Side)

```bash
cd ~/LibraryMaster/mycar
./calibrate_odom.sh                # Calibrate with manual driving
./verify_odom.sh                   # Verify calibration accuracy
# Or one-click: ./calibrate_and_verify.sh
```

#### 3.2 2D Distributed Mapping

**Step 1**: Start car-side sensor pipeline (sends data to PC)

```bash
cd ~/LibraryMaster/mycar
./start_mycar.sh mapping_distributed /dev/ttyUSB0
```

**Step 2**: Start PC-side SLAM + RViz2

```bash
cd ~/LibraryMaster/mycar_pc
./start_pc.sh mapping2d
```

**Step 3**: Drive the car to explore the library

```
Keyboard controls in the terminal:
  i  = forward
  ,  = backward
  j  = turn left
  l  = turn right
  k  = stop
```

**Step 4**: Save map when done

```bash
# In a new terminal on PC side
ros2 run nav2_map_server map_saver_cli -f ~/LibraryMaster/map/mycar_map
```

The map will be saved as `mycar_map.pgm` and `mycar_map.yaml`.

### Phase 4: Waypoint Marking

After saving the map, start navigation mode to mark waypoints.

```bash
# Car side - start navigation with waypoint support
cd ~/LibraryMaster/mycar
./start_mycar.sh waypoint_navigation /dev/ttyUSB0

# PC side - launch monitoring
cd ~/LibraryMaster/mycar_pc
./start_pc.sh nav_monitor
```

**Marking waypoints in RViz2:**
1. Use **2D Pose Estimate** to localize the car on the map
2. Wait for AMCL particles to converge
3. In terminal, set waypoint name: `./scripts/save_waypoint.sh "书架A"`
4. Or use RViz **Publish Point** button:
   ```bash
   ros2 topic pub /set_waypoint_name std_msgs/String "data: '出入口'" --once
   # Then click on map in RViz with Publish Point
   ```
5. Waypoints auto-save to `mycar_map_waypoints.yaml`

### Phase 5: Actual Operation

#### 5.1 Start All Services

**PC Side:**
```bash
# 1. Start embedding service (if not already running)
cd ~/LibraryMaster/Embedding
./start_embedding.sh

# 2. Start RAG API
cd ~/LibraryMaster/rag
docker compose up -d
```

**Car Side (RDK X5):**
```bash
# 1. Start voice agent (Docker + Web UI + voice services)
cd ~/LibraryMaster/voice_agent

# Full service: Docker + Kiosk + KWS + Voice Relay
./start_voice_agent.sh --kws

# With HDMI kiosk display
./start_voice_agent.sh --kiosk

# Or start services separately:
./start_voice_agent.sh                    # Docker only (Agent Server)
# In another terminal:
python3 src/voice_relay.py                # Voice relay (mic recording)
python3 src/kws_service.py                # Wake-up word detection

# 2. Start robot navigation
cd ~/LibraryMaster/mycar
./start_mycar.sh waypoint_navigation /dev/ttyUSB0
```

**PC Side (monitoring):**
```bash
cd ~/LibraryMaster/mycar_pc
./start_pc.sh nav_monitor
```

#### 5.2 Interaction

**Voice Mode (on kiosk):**
- Say **"你好小图"** to wake up
- Speak naturally, e.g., "帮我找一下人工智能的书"
- The agent searches via RAG API and shows results on screen
- Say **"导航到书架A"** to command the robot to navigate

**Text Mode (CLI):**
```bash
cd ~/LibraryMaster/voice_agent
python3 main.py
>>> 帮我找一下深度学习相关的书
```

**REST API (for programmatic access):**
```bash
# Navigate to a waypoint
curl -X POST http://<car-ip>:5000/navigate \
  -H "Content-Type: application/json" \
  -d '{"x": 1.5, "y": 2.0, "yaw": 0.0}'

# Check robot status
curl http://<car-ip>:5000/status

# Cancel navigation
curl -X POST http://<car-ip>:5000/cancel
```

---

## Module Details

### voice_agent/ — Library Voice Agent (Car Side)

| File | Description |
|------|-------------|
| `main.py` | CLI entry point |
| `config.py` | All configuration (API keys, ports, prompts) |
| `kiosk.py` | Full-screen WebKit2GTK kiosk browser (Weston Wayland) |
| `app/agent_server.py` | FastAPI + WebSocket server (port 9015) |
| `app/agent.py` | ReAct agent loop (DeepSeek Function Calling) |
| `app/llm.py` | DeepSeek LLM wrapper with streaming |
| `app/tools.py` | Tool definitions: search_books, get_library_info |
| `app/static/` | Web UI frontend (SPA) |
| `src/voice_relay.py` | HTTP mic recording relay (port 9016) |
| `src/kws_service.py` | Keyword wake-up service ("你好小图") |
| `src/xunfei_asr.py` | iFlytek streaming ASR client |
| `src/xunfei_tts.py` | iFlytek streaming TTS client |
| `docker-compose.yml` | Docker compose for agent server |

### rag/ — RAG Vector Search Service (PC Side)

| File | Description |
|------|-------------|
| `docker-compose.yml` | Docker compose for LanceDB + FastAPI |
| `dockerfile` | Docker image build |
| `src/input.py` | CSV book data import to LanceDB |
| `src/vector_query.py` | Text vectorization + LanceDB search |
| `src/rag_api.py` | FastAPI endpoints (/search, /keyword_search, /query) |
| `src/main.py` | Service entry point |

### Embedding/ — Embedding Service (PC Side)

| File | Description |
|------|-------------|
| `start_embedding.sh` | Start SGLang embedding server |
| `model/` | Qwen3-Embedding-0.6B model files |
| `test/` | Test scripts for embedding API |

### mycar/ — Robot Car ROS2 Workspace (Car Side)

| Directory/File | Description |
|----------------|-------------|
| `src/mycar_driver/` | Driver, odometry, EKF, camera, LaserScan nodes |
| `src/mycar_f/` | URDF robot model (SolidWorks → STL) |
| `src/mycar_slam/` | Local 2D slam_toolbox mapping |
| `src/mycar_rtabmap/` | Local 3D RTAB-Map mapping |
| `src/mycar_navigation/` | Nav2 navigation, waypoint saver, map keepalive |
| `scripts/` | save_waypoint.sh, goto.sh |
| `config/` | Fast-DDS config, nav2 params |
| `calibrate_odom.sh` | Odometry calibration |
| `verify_odom.sh` | Odometry verification |
| `calibrate_and_verify.sh` | One-click calibration + verification |
| `diagnose.sh` | Data pipeline diagnostics |
| `start_mycar.sh` | Unified launcher for all modes |

### mycar_pc/ — PC-side Distributed Mapping

| Directory/File | Description |
|----------------|-------------|
| `src/mycar_rtabmap/` | PC-side SLAM launch files, configs, RViz layouts |
| `src/mycar_f/` | URDF model copy for robot_state_publisher |
| `test_3d_mapping.py` | Data flow test tool for 3D mapping |
| `test_3d_mapping.sh` | One-click test script |
| `start_pc.sh` | Unified launcher (scan_view, mapping2d, mapping3d_rgbd, nav_monitor) |

---

## Quick Reference: Key Commands

### Car Side (RDK X5)

| Action | Command |
|--------|---------|
| Build workspace | `./build.sh` |
| Odometry calibration | `./calibrate_odom.sh` |
| 2D distributed mapping (car) | `./start_mycar.sh mapping_distributed` |
| Navigation + waypoints | `./start_mycar.sh waypoint_navigation` |
| Start voice agent | `cd ../voice_agent && ./start_voice_agent.sh` |
| Start voice + kws | `cd ../voice_agent && ./start_voice_agent.sh --kws` |
| Start voice + kiosk | `cd ../voice_agent && ./start_voice_agent.sh --kiosk` |
| Voice relay only | `cd ../voice_agent && python3 src/voice_relay.py` |
| KWS only | `cd ../voice_agent && python3 src/kws_service.py` |
| Diagnose data | `./diagnose.sh` |
| Save waypoint | `./scripts/save_waypoint.sh "name"` |
| Go to waypoint | `./scripts/goto.sh "name"` |
| Save map | `ros2 run nav2_map_server map_saver_cli -f ~/LibraryMaster/map/mycar_map` |

### PC Side (x86)

| Action | Command |
|--------|---------|
| Build workspace | `./build.sh` |
| Start embedding | `cd ../Embedding && ./start_embedding.sh` |
| Import book data | `cd ../rag && python3 src/input.py` |
| Start RAG API | `cd ../rag && docker compose up -d` |
| 2D distributed mapping (PC) | `./start_pc.sh mapping2d` |
| Navigation monitor | `./start_pc.sh nav_monitor` |
| Data flow test | `./test_3d_mapping.sh` |

---

## License

MIT
