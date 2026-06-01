#pragma once
#include <atomic>
#include <string>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <cstdio>
#include <cstring>

// Parses ASCII frames: "$TEMP,xx.x\r\n" and "$DNI,xxx.x\r\n"
class SerialSensorReader {
public:
    explicit SerialSensorReader(const std::string& device, int baud = B9600)
        : device_(device), baud_(baud) {}

    ~SerialSensorReader() { if (fd_ >= 0) ::close(fd_); }

    bool open() noexcept {
        fd_ = ::open(device_.c_str(), O_RDONLY | O_NOCTTY | O_NONBLOCK);
        if (fd_ < 0) return false;

        struct termios tty{};
        cfsetispeed(&tty, baud_);
        tty.c_cflag = CS8 | CREAD | CLOCAL;
        tty.c_iflag = IGNPAR;
        tty.c_oflag = 0;
        tty.c_lflag = 0;
        return tcsetattr(fd_, TCSANOW, &tty) == 0;
    }

    // Call in a polling loop; returns true if a frame was parsed.
    bool poll() noexcept {
        char c;
        while (::read(fd_, &c, 1) == 1) {
            if (c == '\n') {
                buf_[buf_pos_] = '\0';
                parseFrame(buf_);
                buf_pos_ = 0;
            } else if (c != '\r' && buf_pos_ < kBufSize - 1) {
                buf_[buf_pos_++] = c;
            }
        }
        return false;
    }

    float temperature() const noexcept { return temperature_.load(); }
    float dni()         const noexcept { return dni_.load(); }

private:
    void parseFrame(const char* line) noexcept {
        float val = 0.0f;
        if (std::sscanf(line, "$TEMP,%f", &val) == 1)
            temperature_.store(val);
        else if (std::sscanf(line, "$DNI,%f", &val) == 1)
            dni_.store(val);
    }

    static constexpr int kBufSize = 64;
    std::string          device_;
    int                  baud_;
    int                  fd_       = -1;
    char                 buf_[kBufSize]{};
    int                  buf_pos_  = 0;
    std::atomic<float>   temperature_{0.0f};
    std::atomic<float>   dni_{0.0f};
};
