// 기존 Jazzy 컴포넌트 실행 계약을 유지하고 TBB/라이브러리 종료 순서만 소유한다.
#include <cstdlib>
#include <opencv2/core.hpp>
#include <iostream>
#include <memory>
#include <string>
#include <oneapi/tbb/global_control.h>
#include <class_loader/class_loader.hpp>
#include <rclcpp/rclcpp.hpp>
#include <rclcpp_components/node_factory.hpp>
#include "finalize_order.hpp"

#ifndef COMPONENT_LIBRARY
#error COMPONENT_LIBRARY required
#endif
#ifndef COMPONENT_CLASS
#error COMPONENT_CLASS required
#endif

int main(int argc, char** argv)
{
  // 실행 파일의 DT_NEEDED 참조와 handle을 컴포넌트보다 먼저 확보한다.
  oneapi::tbb::task_scheduler_handle scheduler{oneapi::tbb::attach{}};
  std::unique_ptr<class_loader::ClassLoader> loader;
  std::shared_ptr<rclcpp_components::NodeFactory> factory;
  std::unique_ptr<rclcpp::executors::SingleThreadedExecutor> executor;
  int result = 0;
  try {
    auto args = rclcpp::init_and_remove_ros_arguments(argc, argv);
    rclcpp::NodeOptions options;
    options.arguments(args);
    loader = std::make_unique<class_loader::ClassLoader>(COMPONENT_LIBRARY);
    factory = loader->createInstance<rclcpp_components::NodeFactory>(
      "rclcpp_components::NodeFactoryTemplate<" COMPONENT_CLASS ">");
    executor = std::make_unique<rclcpp::executors::SingleThreadedExecutor>();
    {
      auto wrapper = factory->create_node_instance(options);
      auto node = wrapper.get_node_base_interface();
      executor->add_node(node);
      std::cout << "TBB_SAFE_NODE_READY" << std::endl;
      executor->spin();
      executor->remove_node(node);
    }
  } catch (const std::exception& error) {
    std::cerr << "TBB_SAFE_NODE_ERROR: " << error.what() << std::endl;
    result = 1;
  } catch (...) {
    std::cerr << "TBB_SAFE_NODE_ERROR: unknown exception" << std::endl;
    result = 1;
  }
  // executor가 보유할 수 있는 노드/콜백 참조도 finalize 전에 정리한다.
  executor.reset();
  try { rclcpp::shutdown(); }
  catch (const std::exception& error) {
    std::cerr << "TBB_SAFE_SHUTDOWN_ERROR: " << error.what() << std::endl;
    result = 1;
  }
  // spin 종료 및 node/executor 소멸 이후에만 프로세스 전역 OpenCV arena를 해제한다.
  // 처리 중 병렬도는 바꾸지 않는다. 1은 arena를 다시 만들므로 0을 사용한다.
  try {
    cv::setNumThreads(0);
    std::cout << "OPENCV_ARENA_RELEASED" << std::endl;
  } catch (const std::exception& error) {
    std::cerr << "OPENCV_RELEASE_FAILED: " << error.what() << std::endl;
    std::_Exit(3);
  }
  std::cout << "TBB_FINALIZE_BEGIN" << std::endl;
  const bool finalized = finalize_before_unload(
    [&scheduler]() -> bool {
      const bool ok = oneapi::tbb::finalize(scheduler, std::nothrow);
      if (ok) std::cout << "TBB_FINALIZED" << std::endl;
      return ok;
    },
    [&]() -> void {
      factory.reset();
      loader.reset();
      std::cout << "COMPONENT_LIBRARY_RELEASED" << std::endl;
    });
  if (!finalized) {
    // 실패 시 exit handler의 dlclose 경쟁을 재발시키지 않는다. 성공 종료로 숨기지 않는다.
    std::cerr << "TBB_FINALIZE_FAILED: refusing library unload; exit=3" << std::endl;
    std::_Exit(3);
  }
  return result;
}
