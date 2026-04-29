#!/bin/bash
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"

source /opt/tros/humble/setup.bash
source ./install/setup.bash
ros2 run yahboomcar_bringup Mcnamu_driver_X3
