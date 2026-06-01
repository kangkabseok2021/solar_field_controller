#include <gtest/gtest.h>
#include "../src/PIController.h"
#include "../src/FieldController.h"

// ── PIController ──────────────────────────────────────────────────────────────

TEST(PIController, StepResponse_ConvergesWithin50Ticks) {
    PIController pi;
    float pos = 0.0f;
    for (int i = 0; i < 50; ++i) {
        float out = pi.update(20.0f - pos, 0.1f);
        pos += out * 0.1f;  // first-order integrating plant (vel = control output)
    }
    // After 5 s the position must be within 2° of target
    EXPECT_LT(std::abs(20.0f - pos), 2.0f);
}

TEST(PIController, AntiWindup_ClampsPreventsOvershoot) {
    PIController pi(0.8f, 0.05f, 0.1f, 5.0f, 90.0f);  // small integral limit
    for (int i = 0; i < 100; ++i) pi.update(10.0f, 0.1f);
    EXPECT_LE(std::abs(pi.integral()), 5.0f);
}

TEST(PIController, Deadband_NoOutputBelowThreshold) {
    PIController pi;
    EXPECT_FLOAT_EQ(pi.update(0.05f, 0.1f), 0.0f);   // within ±0.1°
    EXPECT_FLOAT_EQ(pi.update(-0.09f, 0.1f), 0.0f);
}

TEST(PIController, Reset_ZerosIntegral) {
    PIController pi;
    pi.update(30.0f, 0.1f);
    EXPECT_NE(pi.integral(), 0.0f);
    pi.reset();
    EXPECT_FLOAT_EQ(pi.integral(), 0.0f);
}

// ── FieldController FSM ───────────────────────────────────────────────────────

TEST(FSM, Init_TransitionsToTracking_OnHomingComplete) {
    ControllerConfig cfg;
    cfg.home_tolerance_deg   = 1.0f;
    cfg.home_consecutive_ok  = 3;
    FieldController ctrl(cfg);

    ASSERT_EQ(ctrl.state(), FieldState::INIT);
    // Feed encoder ≈ 0 (home position) for 3 ticks
    for (int i = 0; i < 3; ++i)
        ctrl.onTick(0.0f, 0.3f, 0.0f);  // 0.3° < 1.0° tolerance
    EXPECT_EQ(ctrl.state(), FieldState::TRACKING);
}

TEST(FSM, Tracking_TransitionsToWindStow_AboveThreshold) {
    ControllerConfig cfg;
    cfg.home_consecutive_ok = 1;
    FieldController ctrl(cfg);

    // Force into TRACKING
    ctrl.onTick(0.0f, 0.0f, 0.0f);
    ASSERT_EQ(ctrl.state(), FieldState::TRACKING);

    ctrl.onTick(30.0f, 30.0f, 15.0f);  // wind > 12 m/s
    EXPECT_EQ(ctrl.state(), FieldState::WIND_STOW);
}

TEST(FSM, WindStow_IgnoresTargetAngle) {
    ControllerConfig cfg;
    cfg.home_consecutive_ok   = 1;
    cfg.stow_angle_deg        = 90.0f;
    cfg.wind_stow_threshold_ms = 12.0f;
    FieldController ctrl(cfg);

    ctrl.onTick(0.0f, 0.0f, 0.0f);   // → TRACKING
    ctrl.onTick(30.0f, 30.0f, 15.0f); // → WIND_STOW

    // Target angle changes — setpoint should still move toward stow, not target
    float sp = ctrl.onTick(-45.0f, 80.0f, 15.0f);
    EXPECT_GT(sp, 80.0f);  // still heading toward 90°, not -45°
}

TEST(FSM, Fault_OnEncoderTimeout) {
    ControllerConfig cfg;
    cfg.encoder_timeout_ticks = 3;
    cfg.home_consecutive_ok   = 1;
    FieldController ctrl(cfg);

    ctrl.onTick(0.0f, 0.0f, 0.0f);  // → TRACKING
    for (int i = 0; i < 3; ++i) ctrl.onCommLoss();
    EXPECT_EQ(ctrl.state(), FieldState::FAULT);
    EXPECT_EQ(ctrl.faultReason(), "encoder_timeout");
}

TEST(FSM, Fault_CannotTransitionToTracking_Directly) {
    ControllerConfig cfg;
    cfg.encoder_timeout_ticks = 1;
    cfg.home_consecutive_ok   = 1;
    FieldController ctrl(cfg);

    ctrl.onTick(0.0f, 0.0f, 0.0f);
    ctrl.onCommLoss();
    ASSERT_EQ(ctrl.state(), FieldState::FAULT);

    // Restoring comm does not exit FAULT (requires external reset)
    ctrl.onCommRestored();
    ctrl.onTick(0.0f, 0.0f, 0.0f);
    EXPECT_EQ(ctrl.state(), FieldState::FAULT);
}

TEST(FSM, WindStow_ExitsWhenWindDrops) {
    ControllerConfig cfg;
    cfg.home_consecutive_ok    = 1;
    cfg.wind_stow_threshold_ms = 12.0f;
    FieldController ctrl(cfg);

    ctrl.onTick(0.0f, 0.0f, 0.0f);    // → TRACKING
    ctrl.onTick(0.0f, 0.0f, 15.0f);   // → WIND_STOW

    // Wind drops below 80% of threshold (hysteresis)
    for (int i = 0; i < 5; ++i)
        ctrl.onTick(0.0f, 90.0f, 9.0f);  // 9 < 12*0.8=9.6 → exit WIND_STOW
    EXPECT_EQ(ctrl.state(), FieldState::TRACKING);
}
