#pragma once
#include <modbus/modbus.h>
#include <stdexcept>
#include <string>

// Modbus register map (1-based addresses, libmodbus uses 0-based internally)
inline constexpr int kRegSetpoint = 40001 - 1;  // holding register: setpoint ×10
inline constexpr int kRegEncoder  = 30001 - 1;  // input register:   encoder  ×10
inline constexpr int kScaleFactor = 10;

class ModbusDriveClient {
public:
    ModbusDriveClient(const std::string& ip, int port) {
        ctx_ = modbus_new_tcp(ip.c_str(), port);
        if (!ctx_) throw std::runtime_error("modbus_new_tcp failed");
        modbus_set_response_timeout(ctx_, 0, 50'000);  // 50 ms
    }

    ~ModbusDriveClient() {
        if (ctx_) { modbus_close(ctx_); modbus_free(ctx_); }
    }

    ModbusDriveClient(const ModbusDriveClient&)            = delete;
    ModbusDriveClient& operator=(const ModbusDriveClient&) = delete;

    bool connect() noexcept {
        return modbus_connect(ctx_) == 0;
    }

    bool setSetpoint(float deg) noexcept {
        uint16_t val = static_cast<uint16_t>(
            static_cast<int>(deg * kScaleFactor));
        return modbus_write_register(ctx_, kRegSetpoint, val) == 1;
    }

    bool readEncoder(float& deg_out) noexcept {
        uint16_t val = 0;
        if (modbus_read_input_registers(ctx_, kRegEncoder, 1, &val) != 1)
            return false;
        deg_out = static_cast<float>(static_cast<int16_t>(val)) / kScaleFactor;
        return true;
    }

private:
    modbus_t* ctx_ = nullptr;
};
