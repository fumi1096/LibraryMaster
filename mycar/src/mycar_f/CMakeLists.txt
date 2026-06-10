cmake_minimum_required(VERSION 3.8)
project(mycar_f)

# Prevent ament_cmake from trying to compile source files
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(ament_cmake REQUIRED)

# Install all resource directories to the package share folder
foreach(dir config launch meshes urdf)
  install(DIRECTORY ${dir}/
    DESTINATION share/${PROJECT_NAME}/${dir})
endforeach(dir)

ament_package()
