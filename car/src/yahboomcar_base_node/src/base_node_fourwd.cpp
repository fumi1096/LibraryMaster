/**
 * base_node_fourwd.cpp
 * 四驱普通轮子（差速驱动）里程计节点
 *
 * 功能：
 * 1. 订阅 vel_raw 话题，获取驱动节点发布的原始速度数据
 * 2. 根据差速驱动运动学模型积分计算里程计（位姿估计）
 * 3. 发布 Odometry 消息到 /odom_raw 话题
 * 4. 可选发布 odom → base_footprint 的 TF 变换
 *
 * 与 base_node_X3 的区别：
 * - 适用于四轮独立驱动、差速转向的普通轮小车
 * - vy（横向速度）始终为 0，不做横向运动学处理
 * - child_frame_id 为 base_footprint（与 mycar00 URDF 匹配）
 */

#include <geometry_msgs/msg/transform_stamped.hpp>
#include "geometry_msgs/msg/twist.hpp"
#include "nav_msgs/msg/odometry.hpp"

#include <rclcpp/rclcpp.hpp>
#include <tf2/LinearMath/Quaternion.h>
#include <tf2_ros/transform_broadcaster.h>

#include <memory>
#include <string>

#include <chrono>
#include <functional>
#include <memory>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
using std::placeholders::_1;

class OdomPublisher : public rclcpp::Node
{
    rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr subscription_;
    rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr odom_publisher_;
    std::unique_ptr<tf2_ros::TransformBroadcaster> tf_broadcaster_;
    double linear_scale_x_ = 0.0;
    double linear_scale_y_ = 0.0;
    double vel_dt_ = 0.0;
    double x_pos_ = 0.0;
    double y_pos_ = 0.0;
    double heading_ = 0.0;
    double linear_velocity_x_ = 0.0;
    double linear_velocity_y_ = 0.0;
    double angular_velocity_z_ = 0.0;
    double wheelbase_ = 0.25;
    bool pub_odom_tf_ = false;
    rclcpp::Time last_vel_time_;

public:
    OdomPublisher()
        : Node("base_node")
    {
        // 声明参数
        this->declare_parameter<double>("wheelbase", 0.25);
        this->declare_parameter<std::string>("odom_frame", "odom");
        this->declare_parameter<std::string>("base_footprint_frame", "base_footprint");
        this->declare_parameter<double>("linear_scale_x", 1.0);
        this->declare_parameter<double>("linear_scale_y", 1.0);
        this->declare_parameter<bool>("pub_odom_tf", true);

        // 读取参数
        this->get_parameter<double>("linear_scale_x", linear_scale_x_);
        this->get_parameter<double>("linear_scale_y", linear_scale_y_);
        this->get_parameter<double>("wheelbase", wheelbase_);
        this->get_parameter<bool>("pub_odom_tf", pub_odom_tf_);

        tf_broadcaster_ = std::make_unique<tf2_ros::TransformBroadcaster>(*this);

        // 订阅驱动节点发布的原始速度数据
        subscription_ = this->create_subscription<geometry_msgs::msg::Twist>(
            "vel_raw", 50, std::bind(&OdomPublisher::handle_vel, this, _1));

        // 发布里程计数据
        odom_publisher_ = this->create_publisher<nav_msgs::msg::Odometry>("/odom_raw", 50);
    }

private:
    /**
     * 速度数据回调：执行里程计积分计算
     *
     * 运动学模型（差速驱动）：
     *   delta_heading = angular_velocity_z * dt
     *   delta_x = (vx * cos(heading) - vy * sin(heading)) * dt
     *   delta_y = (vx * sin(heading) + vy * cos(heading)) * dt
     *
     * 对于四驱普通轮子，vy = 0，公式简化为：
     *   delta_x = vx * cos(heading) * dt
     *   delta_y = vx * sin(heading) * dt
     */
    void handle_vel(const std::shared_ptr<geometry_msgs::msg::Twist> msg)
    {
        rclcpp::Time curren_time = rclcpp::Clock().now();

        linear_velocity_x_ = msg->linear.x * linear_scale_x_; // 前进速度
        linear_velocity_y_ = msg->linear.y * linear_scale_y_; // 四驱普通轮：始终为0
        angular_velocity_z_ = msg->angular.z;                // 旋转角速度

        vel_dt_ = (curren_time - last_vel_time_).seconds();
        last_vel_time_ = curren_time;

        // 差速驱动运动学积分
        double delta_heading = angular_velocity_z_ * vel_dt_; // 角度变化（弧度）
        double delta_x = (linear_velocity_x_ * cos(heading_) -
                          linear_velocity_y_ * sin(heading_)) *
                         vel_dt_; // X方向位移
        double delta_y = (linear_velocity_x_ * sin(heading_) +
                          linear_velocity_y_ * cos(heading_)) *
                         vel_dt_; // Y方向位移

        x_pos_ += delta_x;
        y_pos_ += delta_y;
        heading_ += delta_heading;

        // 将偏航角转换为四元数
        tf2::Quaternion myQuaternion;
        geometry_msgs::msg::Quaternion odom_quat;
        myQuaternion.setRPY(0.00, 0.00, heading_);

        odom_quat.x = myQuaternion.x();
        odom_quat.y = myQuaternion.y();
        odom_quat.z = myQuaternion.z();
        odom_quat.w = myQuaternion.w();

        // === 发布里程计消息 ===
        nav_msgs::msg::Odometry odom;
        odom.header.stamp = curren_time;
        odom.header.frame_id = "odom";
        odom.child_frame_id = "base_footprint";

        // 位姿
        odom.pose.pose.position.x = x_pos_;
        odom.pose.pose.position.y = y_pos_;
        odom.pose.pose.position.z = 0.0;
        odom.pose.pose.orientation = odom_quat;
        odom.pose.covariance[0] = 0.001;
        odom.pose.covariance[7] = 0.001;
        odom.pose.covariance[35] = 0.001;

        // 速度
        odom.twist.twist.linear.x = linear_velocity_x_;
        odom.twist.twist.linear.y = 0.0; // 四驱普通轮：无横向速度
        odom.twist.twist.linear.z = 0.0;
        odom.twist.twist.angular.x = 0.0;
        odom.twist.twist.angular.y = 0.0;
        odom.twist.twist.angular.z = angular_velocity_z_;
        odom.twist.covariance[0] = 0.0001;
        odom.twist.covariance[7] = 0.0001;
        odom.twist.covariance[35] = 0.0001;

        odom_publisher_->publish(odom);

        // === 可选：发布 TF odom → base_footprint ===
        if (pub_odom_tf_)
        {
            geometry_msgs::msg::TransformStamped t;
            rclcpp::Time now = this->get_clock()->now();
            t.header.stamp = now;
            t.header.frame_id = "odom";
            t.child_frame_id = "base_footprint";
            t.transform.translation.x = x_pos_;
            t.transform.translation.y = y_pos_;
            t.transform.translation.z = 0.0;

            t.transform.rotation.x = myQuaternion.x();
            t.transform.rotation.y = myQuaternion.y();
            t.transform.rotation.z = myQuaternion.z();
            t.transform.rotation.w = myQuaternion.w();

            tf_broadcaster_->sendTransform(t);
        }
    }
};

int main(int argc, char *argv[])
{
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<OdomPublisher>());
    rclcpp::shutdown();
    return 0;
}
