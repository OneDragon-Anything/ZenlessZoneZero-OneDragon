#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <iostream>
#include <memory>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>

#include <pqrs/dispatcher.hpp>
#include <pqrs/karabiner/driverkit/virtual_hid_device_driver.hpp>
#include <pqrs/karabiner/driverkit/virtual_hid_device_service.hpp>

namespace {

using Client = pqrs::karabiner::driverkit::virtual_hid_device_service::client;
using PointingInput = pqrs::karabiner::driverkit::virtual_hid_device_driver::hid_report::pointing_input;

std::mutex state_mutex;
std::condition_variable state_changed;
bool pointing_ready = false;
std::string startup_error;

void set_startup_error(const std::string& message) {
  std::lock_guard<std::mutex> lock(state_mutex);
  if (startup_error.empty()) {
    startup_error = message;
  }
  state_changed.notify_all();
}

void stop_client(std::unique_ptr<Client>& client) {
  if (client) {
    PointingInput release_report;
    client->async_post_report(release_report);
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
    client->async_stop();
    client.reset();
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
  }
  pqrs::dispatcher::extra::terminate_shared_dispatcher();
}

int run() {
  pqrs::dispatcher::extra::initialize_shared_dispatcher();

  auto client = std::make_unique<Client>();
  client->connected.connect([&client] {
    client->async_virtual_hid_pointing_initialize();
  });
  client->connect_failed.connect([](const auto& error_code) {
    set_startup_error("无法连接 Karabiner 虚拟 HID 服务: " + error_code.message());
  });
  client->error_occurred.connect([](const auto& error_code) {
    set_startup_error("Karabiner 虚拟 HID 服务错误: " + error_code.message());
  });
  client->virtual_hid_pointing_ready.connect([](bool ready) {
    std::lock_guard<std::mutex> lock(state_mutex);
    pointing_ready = ready;
    state_changed.notify_all();
  });
  client->driver_version_mismatched.connect([](bool mismatched) {
    if (mismatched) {
      set_startup_error("Karabiner 虚拟 HID 客户端与驱动版本不匹配");
    }
  });
  client->async_start();

  {
    std::unique_lock<std::mutex> lock(state_mutex);
    state_changed.wait_for(lock, std::chrono::seconds(10), [] {
      return pointing_ready || !startup_error.empty();
    });
    if (!pointing_ready) {
      const auto message = startup_error.empty()
                               ? "虚拟鼠标设备未就绪，请确认 Karabiner 虚拟 HID 驱动已安装并运行"
                               : startup_error;
      std::cout << "ERROR " << message << std::endl;
      lock.unlock();
      stop_client(client);
      return 1;
    }
  }

  std::cout << "READY" << std::endl;

  uint32_t buttons_state = 0;
  std::string line;
  while (std::getline(std::cin, line)) {
    if (line == "quit") {
      break;
    }

    std::istringstream input(line);
    std::string command;
    unsigned int button = 0;
    unsigned int duration_ms = 0;
    std::string trailing;
    if (!(input >> command >> button >> duration_ms) ||
        input >> trailing ||
        (command != "click" && command != "press" && command != "release") ||
        (button < 1 || button > 3) ||
        (command == "click" && (duration_ms < 1 || duration_ms > 60000)) ||
        (command != "click" && duration_ms != 0)) {
      std::cout << "ERROR 无效的虚拟鼠标命令" << std::endl;
      continue;
    }

    {
      std::lock_guard<std::mutex> lock(state_mutex);
      if (!startup_error.empty() || !pointing_ready) {
        std::cout << "ERROR "
                  << (startup_error.empty() ? "虚拟鼠标设备已断开" : startup_error)
                  << std::endl;
        continue;
      }
    }

    const uint32_t button_mask = 1u << (button - 1);
    const bool was_pressed = (buttons_state & button_mask) != 0;
    if (command == "click" || command == "press") {
      buttons_state |= button_mask;
    } else {
      buttons_state &= ~button_mask;
    }

    PointingInput report;
    for (uint8_t report_button = 1; report_button <= 3; ++report_button) {
      if ((buttons_state & (1u << (report_button - 1))) != 0) {
        report.buttons.insert(report_button);
      }
    }
    client->async_post_report(report);

    if (command == "click") {
      std::this_thread::sleep_for(std::chrono::milliseconds(duration_ms));
      if (!was_pressed) {
        buttons_state &= ~button_mask;
      }

      PointingInput release_report;
      for (uint8_t report_button = 1; report_button <= 3; ++report_button) {
        if ((buttons_state & (1u << (report_button - 1))) != 0) {
          release_report.buttons.insert(report_button);
        }
      }
      client->async_post_report(release_report);
    }
    std::cout << "OK" << std::endl;
  }

  stop_client(client);
  return 0;
}

}

int main() {
  return run();
}
