#include <cmath>
#include <limits>
#include "gtest/gtest.h"
#include "farm_nav2_controller/reverse_regulated_pure_pursuit_controller.hpp"
class ReverseProbe : public farm_nav2_controller::ReverseRegulatedPurePursuitController {
public:
  using ReverseRegulatedPurePursuitController::skipApproachRotation;
  void select(bool enabled) {_skip_position_approach_rotation = enabled;}
  using ReverseRegulatedPurePursuitController::curvaturePoint;
  nav2_regulated_pure_pursuit_controller::Parameters values{};
  ReverseProbe() {params_ = &values;}
  void work(bool enabled) {
    _use_work_curvature = enabled;
    values.use_fixed_curvature_lookahead = true;
    values.curvature_lookahead_dist = .4;
    values.interpolate_curvature_after_goal = true;
  }
};
TEST(ReverseApproach, WorkCurvatureExtendsReverseTangentOnlyWhenSelected) {
  ReverseProbe p;
  nav_msgs::msg::Path path;
  for (double x : {0., -.04, -.08}) {
    geometry_msgs::msg::PoseStamped point;
    point.pose.position.x = x;
    point.pose.position.y = .02;
    point.pose.orientation.w = 1.;
    path.poses.push_back(point);
  }
  auto original = path.poses.back().pose.position;
  p.work(false);
  EXPECT_DOUBLE_EQ(p.curvaturePoint(path, original).x, original.x);
  p.work(true);
  const auto extended = p.curvaturePoint(path, original);
  EXPECT_LT(extended.x, -.39);
  EXPECT_NEAR(extended.y, .02, 1e-10);
  EXPECT_NEAR(std::hypot(extended.x, extended.y), .4, 1e-10);
  p.values.interpolate_curvature_after_goal = false;
  EXPECT_DOUBLE_EQ(p.curvaturePoint(path, original).x, original.x);
  p.values.use_fixed_curvature_lookahead = false;
  EXPECT_DOUBLE_EQ(p.curvaturePoint(path, original).x, original.x);
}
TEST(ReverseApproach, DefaultKeepsExistingAlignment) {
  ReverseProbe p;
  EXPECT_FALSE(p.skipApproachRotation(.05, .4, M_PI));
}
TEST(ReverseApproach, OnlyPositionGoalWithinExistingLookahead) {
  ReverseProbe p; p.select(true);
  EXPECT_TRUE(p.skipApproachRotation(.05, .4, M_PI));
  EXPECT_TRUE(p.skipApproachRotation(.4, .4, -M_PI));
  EXPECT_FALSE(p.skipApproachRotation(.401, .4, M_PI));
  EXPECT_FALSE(p.skipApproachRotation(.05, .4, .10472));
  EXPECT_FALSE(p.skipApproachRotation(.05, .4, .05));
  EXPECT_FALSE(p.skipApproachRotation(-.05, .4, M_PI));
  EXPECT_FALSE(p.skipApproachRotation(.05, 0., M_PI));
  EXPECT_FALSE(p.skipApproachRotation(std::numeric_limits<double>::quiet_NaN(), .4, M_PI));
}
