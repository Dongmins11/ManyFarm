#pragma once
#include <utility>

// 작업 스레드 종료 확인이 실패하거나 예외가 발생하면 라이브러리를 해제하지 않는다.
template<class Finalize, class Unload>
bool finalize_before_unload(Finalize&& finalize, Unload&& unload)
{
  if (!std::forward<Finalize>(finalize)()) return false;
  std::forward<Unload>(unload)();
  return true;
}
