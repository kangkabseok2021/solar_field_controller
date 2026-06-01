#pragma once
#include <algorithm>

inline constexpr float kKp             = 0.8f;
inline constexpr float kKi             = 0.05f;
inline constexpr float kDeadband       = 0.1f;   // degrees — no output within ±0.1°
inline constexpr float kIntegralLimit  = 50.0f;  // anti-windup clamp
inline constexpr float kOutputLimit    = 90.0f;  // max drive angle ±90°

class PIController {
public:
    PIController(float kp = kKp, float ki = kKi,
                 float deadband = kDeadband,
                 float integral_limit = kIntegralLimit,
                 float output_limit   = kOutputLimit)
        : kp_(kp), ki_(ki), deadband_(deadband),
          integral_limit_(integral_limit), output_limit_(output_limit) {}

    float update(float error, float dt_s) noexcept {
        if (std::abs(error) < deadband_) return 0.0f;

        integral_ += error * dt_s;
        integral_  = std::clamp(integral_, -integral_limit_, integral_limit_);

        float output = kp_ * error + ki_ * integral_;
        return std::clamp(output, -output_limit_, output_limit_);
    }

    void reset() noexcept { integral_ = 0.0f; }

    float integral() const noexcept { return integral_; }

private:
    float kp_, ki_, deadband_, integral_limit_, output_limit_;
    float integral_ = 0.0f;
};
