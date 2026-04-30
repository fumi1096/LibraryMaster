#!/bin/bash
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"
ssh yili@172.24.241.3 "bash -l -c '/home/yili/project/LibraryMaster/start.sh'"
