# Device video playback smoothness

## Goal

Improve forward, rewind, and seek playback while preserving the existing API contract.

## Requirements

- Main entry: `src/views/plugIn/accidentAnalysis.vue`.
- Shared player: `src/components/DualCameraLivePlayer.vue`.
- Management reference only: `src/views/dualCameraDevices/dualCameraSetting.vue`.
- Diagnostic reference only: `public/video-command-test/app.js`.

The following files are forbidden implementation targets:

- `src/views/device/replacementSettlement.vue`
- `src/views/device/iotPoolMonitor.vue`

## Acceptance Criteria

1. Forward playback
   - Send one existing playback control request.
   - Only the latest asynchronous response may update UI state.
2. Rewind and seek
   - Rebuild the player subscription after a successful position change.
   - Stop, close, channel switch, and destroy retain paired cleanup.

## Constraints

- Do not change existing playback API paths, fields, or responses.
