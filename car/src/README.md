sudo apt update
sudo apt install python3-colcon-common-extensions
sudo apt install ros-humble-geographic-*
sudo apt install libgeograph
sudo apt-get install ros-kinetic-robot-localization


下载亚博智能提供的stm32源码
[链接](https://github.com/cra-ros-pkg/robot_localization/tree/rolling-devel)
 src/
    yahboomcar_base_node/
    yahboomcar_bringup/
    yahboomcar_ctrl/
    yahboomcar_description/

安装Rosmaster_Lib库
sudo python3 setup.py install
运行build.sh编译
bash build.sh

# 1. 创建规则文件
确定串口位置
echo 'KERNEL=="ttyUSB*", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE:="0777", SYMLINK+="myserial"' | sudo tee /etc/udev/rules.d/99-rosmaster.rules
