#pragma once
#include "PIController.h"
#include <mutex>
#include <string>

enum class FieldState { INIT, TRACKING, WIND_STOW, FAULT };

inline const char* state_name(FieldState s) noexcept {
    switch (s) {
        case FieldState::INIT:      return "INIT";
        case FieldState::TRACKING:  return "TRACKING";
        case FieldState::WIND_STOW: return "WIND_STOW";
        case FieldState::FAULT:     return "FAULT";
    }
    return "UNKNOWN";
}

struct ControllerConfig {
    float wind_stow_threshold_ms = 12.0f;  // m/s
    float home_tolerance_deg     = 0.5f;
    int   home_consecutive_ok    = 3;
    int   encoder_timeout_ticks  = 5;      // ticks @ 100 ms = 500 ms
    float stow_angle_deg         = 90.0f;
    float dt_s                   = 0.1f;
};

class FieldController {
public:
    explicit FieldController(ControllerConfig cfg = {}) : cfg_(cfg) {}

    // Called every timerfd tick; returns drive setpoint in degrees.
    float onTick(float target_angle, float encoder_feedback,
                 float wind_speed_ms) noexcept {
        std::lock_guard<std::mutex> lk(mtx_);

        // Wind stow takes priority from any state except FAULT
        if (state_ != FieldState::FAULT && wind_speed_ms > cfg_.wind_stow_threshold_ms) {
            if (state_ != FieldState::WIND_STOW) transitionTo(FieldState::WIND_STOW);
        }

        switch (state_) {
            case FieldState::INIT:
                return handleInit(encoder_feedback);
            case FieldState::TRACKING:
                return handleTracking(target_angle, encoder_feedback);
            case FieldState::WIND_STOW:
                return handleWindStow(encoder_feedback, wind_speed_ms);
            case FieldState::FAULT:
                return 0.0f;
        }
        return 0.0f;
    }

    void onCommLoss() noexcept {
        std::lock_guard<std::mutex> lk(mtx_);
        ++encoder_timeout_count_;
        if (encoder_timeout_count_ >= cfg_.encoder_timeout_ticks) {
            fault_reason_ = "encoder_timeout";
            transitionTo(FieldState::FAULT);
        }
    }

    void onCommRestored() noexcept {
        std::lock_guard<std::mutex> lk(mtx_);
        encoder_timeout_count_ = 0;
    }

    FieldState state() const noexcept {
        std::lock_guard<std::mutex> lk(mtx_);
        return state_;
    }

    std::string faultReason() const noexcept {
        std::lock_guard<std::mutex> lk(mtx_);
        return fault_reason_;
    }

private:
    void transitionTo(FieldState next) noexcept {
        state_ = next;
        pi_.reset();
        home_ok_count_ = 0;
        if (next != FieldState::FAULT) encoder_timeout_count_ = 0;
    }

    float handleInit(float encoder) noexcept {
        float error = 0.0f - encoder;  // home position
        if (std::abs(error) < cfg_.home_tolerance_deg) {
            if (++home_ok_count_ >= cfg_.home_consecutive_ok)
                transitionTo(FieldState::TRACKING);
        } else {
            home_ok_count_ = 0;
        }
        return pi_.update(error, cfg_.dt_s);
    }

    float handleTracking(float target, float encoder) noexcept {
        float error  = target - encoder;
        float output = pi_.update(error, cfg_.dt_s);
        return encoder + output;  // absolute setpoint
    }

    float handleWindStow(float encoder, float wind_speed_ms) noexcept {
        // Stay in WIND_STOW until wind drops below threshold
        if (wind_speed_ms <= cfg_.wind_stow_threshold_ms * 0.8f)  // hysteresis
            transitionTo(FieldState::TRACKING);
        float error = cfg_.stow_angle_deg - encoder;
        return encoder + pi_.update(error, cfg_.dt_s);
    }

    mutable std::mutex mtx_;
    FieldState    state_                 = FieldState::INIT;
    PIController  pi_;
    ControllerConfig cfg_;
    int           home_ok_count_         = 0;
    int           encoder_timeout_count_ = 0;
    std::string   fault_reason_;
};
