#include "FieldController.h"
#include "ModbusDriveClient.h"
#include "SerialSensorReader.h"
#include <sys/timerfd.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <sched.h>
#include <unistd.h>
#include <csignal>
#include <cstring>
#include <ctime>
#include <iostream>
#include <stdexcept>

static volatile bool g_running = true;

static void sighandler(int) noexcept { g_running = false; }

// POSIX shared memory layout — written by Python sun-position engine
struct ShmTarget {
    float target_angle;   // degrees, solar tracking setpoint
    float wind_speed_ms;  // m/s, from anemometer
};

static constexpr const char* kShmName      = "/solar_target";
static constexpr const char* kModbusIp     = "127.0.0.1";
static constexpr int         kModbusPort   = 5020;
static constexpr const char* kSerialDevice = "/dev/ttyRS485";
static constexpr long        kPeriodMs     = 100;

static int make_timerfd(long period_ms) {
    int fd = timerfd_create(CLOCK_MONOTONIC, 0);
    if (fd < 0) throw std::runtime_error("timerfd_create failed");
    itimerspec its{};
    its.it_value.tv_nsec    = period_ms * 1'000'000L;
    its.it_interval.tv_nsec = period_ms * 1'000'000L;
    timerfd_settime(fd, 0, &its, nullptr);
    return fd;
}

int main() {
    std::signal(SIGINT,  sighandler);
    std::signal(SIGTERM, sighandler);

    // RT scheduling
    sched_param sp{.sched_priority = 60};
    sched_setscheduler(0, SCHED_FIFO, &sp);

    // Shared memory (target angle from Python sun-position engine)
    int shm_fd = shm_open(kShmName, O_CREAT | O_RDWR, 0600);
    if (ftruncate(shm_fd, sizeof(ShmTarget)) < 0) { perror("ftruncate"); return 1; }
    auto* shm = static_cast<ShmTarget*>(
        mmap(nullptr, sizeof(ShmTarget), PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd, 0));
    shm->target_angle  = 0.0f;
    shm->wind_speed_ms = 0.0f;

    FieldController  controller;
    ModbusDriveClient drive(kModbusIp, kModbusPort);
    SerialSensorReader serial(kSerialDevice);

    if (!drive.connect()) std::cerr << "[WARN] Modbus connect failed — retrying in loop\n";
    serial.open();

    int tfd = make_timerfd(kPeriodMs);

    while (g_running) {
        uint64_t expirations = 0;
        if (read(tfd, &expirations, sizeof(expirations)) < 0) break;

        if (expirations > 1)
            std::cerr << "[WARN] timerfd overrun: " << expirations << " ticks\n";

        serial.poll();

        float encoder = 0.0f;
        if (!drive.readEncoder(encoder)) {
            controller.onCommLoss();
        } else {
            controller.onCommRestored();
        }

        float setpoint = controller.onTick(
            shm->target_angle,
            encoder,
            shm->wind_speed_ms);

        drive.setSetpoint(setpoint);

        if (controller.state() == FieldState::FAULT) {
            std::cerr << "[FAULT] " << controller.faultReason() << '\n';
        }
    }

    close(tfd);
    munmap(shm, sizeof(ShmTarget));
    close(shm_fd);
    shm_unlink(kShmName);
    return 0;
}
