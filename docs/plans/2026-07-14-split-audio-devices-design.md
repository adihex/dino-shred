# Design: Split Audio Devices Support

We need to support audio interfaces that expose separate input and output devices under the macOS Core Audio framework (e.g., "USB AUDIO  CODEC" where device 0 is output-only and device 1 is input-only).

## Proposed Changes

### Audio Engine (`dino_shred/audio/engine.py`)

1. **`find_device` function**:
   - Update it to scan available devices.
   - If a single device with the matching name has both input channels (>= 2) and output channels (>= 2), return its index.
   - If there isn't a single duplex device, find the index of the first input-capable device (>= 2 inputs) matching the name, and the first output-capable device (>= 2 outputs) matching the name. Return them as a tuple `(input_idx, output_idx)`.
   - If neither is found, raise `DeviceNotFoundError`.

2. **`AudioEngine.start()`**:
   - Check if `self.device` is a tuple/list of length 2.
   - If it is, pass it directly as `device=self.device` to `sd.Stream`.
   - Otherwise, pass `device=(self.device, self.device)`.

### Command Line Parsers (`dino_shred/audio/check.py` and `dino_shred/game/app.py`)

1. Update the `--device` CLI argument to accept a string (instead of `int`).
2. Add a helper function to parse this string:
   - If the string contains a comma (e.g., `"1,0"`), split it and return `(int(input), int(output))`.
   - If it can be parsed as a single integer, return `int(val)`.
   - Otherwise, treat it as a name substring to search for (e.g., `"USB AUDIO  CODEC"`).

## Verification Plan

### Manual Verification
1. Run `uv run python -m dino_shred.audio.check --device "USB AUDIO  CODEC"` to verify auto-pairing.
2. Run `uv run python -m dino_shred.audio.check --device 1,0` to verify explicit tuple override.
3. Run the main game using `uv run python -m dino_shred --device "USB AUDIO  CODEC"`.
