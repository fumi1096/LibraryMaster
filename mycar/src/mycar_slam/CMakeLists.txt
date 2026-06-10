cmake_minimum_required(VERSION 3.8)
project(mycar_slam)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(ament_cmake REQUIRED)

# 安装 launch 和 config 目录
install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME})

ament_package()
