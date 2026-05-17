#!/bin/bash
# 双目深度摄像头节点启动脚本

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"

sudo cp -rv /opt/tros/humble/share/hobot_stereonet/script/run_stereo.sh ./
sudo bash run_stereo.sh --mipi_rotation 0.0 --stereonet_frame_id camera_Link