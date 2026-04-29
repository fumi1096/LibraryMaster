sudo apt update
sudo apt install python3-colcon-common-extensions
sudo apt install ros-humble-geographic-*
sudo apt install libgeograph
sudo apt-get install ros-kinetic-robot-localization


下载亚博智能提供的stm32源码
安装Rosmaster_Lib库
sudo python3 setup.py install
运行build.sh编译
bash build.sh

# 1. 创建规则文件
# 这里我们假设你的设备是常见的 CH340 芯片 (亚博常用)。
# 如果你的设备是其他芯片，ID 可能需要调整。
echo 'KERNEL=="ttyUSB*", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE:="0777", SYMLINK+="myserial"' | sudo tee /etc/udev/rules.d/99-rosmaster.rules
