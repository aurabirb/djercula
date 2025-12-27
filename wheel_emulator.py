"""
Steering Wheel Emulator Module
Maps Hercules DJControl inputs to a virtual steering wheel using evdev/uinput.
Linux only.
"""

from dataclasses import dataclass
from typing import Optional, Any

# Sensitivity: how many jog ticks for full steering lock
JOG_STEERING_SENSITIVITY = 1 / 360.0  # Full rotation = full lock

try:
    from evdev import UInput, AbsInfo, ecodes as e
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False
    e = None


@dataclass 
class WheelState:
    """Current state of the virtual wheel"""
    steering: float = 0.0      # -1.0 (left) to 1.0 (right)
    throttle: float = 0.0      # 0.0 to 1.0
    brake: float = 0.0         # 0.0 to 1.0
    clutch: float = 0.0        # 0.0 to 1.0
    gear_up: bool = False
    gear_down: bool = False
    handbrake: bool = False


class WheelEmulator:
    """
    Emulates a steering wheel using DJ controller inputs via evdev/uinput.
    
    Mappings:
    - Jog wheel A (when touched) -> Steering (-32767 to 32767)
    - Pitch slider A -> Throttle (0-255) 
    - Pitch slider B -> Brake (0-255)
    - Volume slider A -> Clutch (0-255)
    - Deck A pad 2 -> Gear Up
    - Deck A pad 6 -> Gear Down
    - Deck A pad 5 -> Handbrake
    - Crossfader -> Fine steering adjustment
    """
    
    # Steering wheel axis range
    STEERING_MIN = -32767
    STEERING_MAX = 32767
    PEDAL_MIN = 0
    PEDAL_MAX = 255
    
    def __init__(self):
        self.device: Optional[Any] = None
        self.enabled: bool = False
        self.state = WheelState()
        
        # Jog wheel tracking
        self._last_jog_a: int = 0
        self._jog_push_a: bool = False
        self._steering_cumulative: float = 0.0
        
        # Button state tracking (for edge detection)
        self._last_gear_up: bool = False
        self._last_gear_down: bool = False
    
    @property
    def available(self) -> bool:
        """Check if evdev is available"""
        return EVDEV_AVAILABLE
    
    def start(self) -> bool:
        """Start the steering wheel emulation"""
        if not EVDEV_AVAILABLE:
            return False
        
        try:
            # Define wheel capabilities
            capabilities = {
                e.EV_ABS: [
                    # Steering wheel axis
                    (e.ABS_WHEEL, AbsInfo(
                        value=0,
                        min=self.STEERING_MIN,
                        max=self.STEERING_MAX,
                        fuzz=0,
                        flat=0,
                        resolution=0
                    )),
                    # Throttle pedal
                    (e.ABS_GAS, AbsInfo(
                        value=0,
                        min=self.PEDAL_MIN,
                        max=self.PEDAL_MAX,
                        fuzz=0,
                        flat=0,
                        resolution=0
                    )),
                    # Brake pedal
                    (e.ABS_BRAKE, AbsInfo(
                        value=0,
                        min=self.PEDAL_MIN,
                        max=self.PEDAL_MAX,
                        fuzz=0,
                        flat=0,
                        resolution=0
                    )),
                    # Clutch pedal (using Z axis)
                    (e.ABS_Z, AbsInfo(
                        value=0,
                        min=self.PEDAL_MIN,
                        max=self.PEDAL_MAX,
                        fuzz=0,
                        flat=0,
                        resolution=0
                    )),
                ],
                e.EV_KEY: [
                    e.BTN_GEAR_UP,
                    e.BTN_GEAR_DOWN,
                    e.BTN_0,  # Handbrake
                    e.BTN_1,  # Extra button
                    e.BTN_2,  # Extra button
                    e.BTN_3,  # Extra button
                ],
            }
            
            # Create virtual device with Logitech-like vendor ID for better compatibility
            self.device = UInput(
                capabilities,
                name="Virtual Racing Wheel",
                vendor=0x046d,   # Logitech vendor ID
                product=0xc294,  # Generic wheel product ID
                version=0x0001,
            )
            
            self.enabled = True
            self._reset_state()
            return True
            
        except Exception as ex:
            print(f"Failed to create virtual wheel: {ex}")
            return False
    
    def stop(self):
        """Stop the steering wheel emulation"""
        if self.device:
            try:
                # Reset all axes to neutral
                self.device.write(e.EV_ABS, e.ABS_WHEEL, 0)
                self.device.write(e.EV_ABS, e.ABS_GAS, 0)
                self.device.write(e.EV_ABS, e.ABS_BRAKE, 0)
                self.device.write(e.EV_ABS, e.ABS_Z, 0)
                self.device.syn()
                self.device.close()
            except Exception:
                pass
            self.device = None
        self.enabled = False
    
    def _reset_state(self):
        """Reset all controls to neutral"""
        self.state = WheelState()
        self._steering_cumulative = 0.0
        self._last_jog_a = 0
        self._jog_push_a = False
        self._last_gear_up = False
        self._last_gear_down = False
        
        if self.device:
            self.device.write(e.EV_ABS, e.ABS_WHEEL, 0)
            self.device.write(e.EV_ABS, e.ABS_GAS, 0)
            self.device.write(e.EV_ABS, e.ABS_BRAKE, 0)
            self.device.write(e.EV_ABS, e.ABS_Z, 0)
            self.device.syn()
    
    def update_from_app(self, app):
        """
        Update wheel state from DJControlApp state.
        Call this after processing MIDI messages.
        """
        if not self.enabled or not self.device:
            return
        
        # Handle jog wheel touch state
        jog_push_changed = app.jog_push_a != self._jog_push_a
        self._jog_push_a = app.jog_push_a
        
        if jog_push_changed and app.jog_push_a:
            # Just touched - reset steering to center
            self._steering_cumulative = 0.0
            self._last_jog_a = app.deck_a_jogwheel
        
        # Handle jog wheel rotation -> Steering
        if self._jog_push_a:
            delta = app.deck_a_jogwheel - self._last_jog_a
            self._last_jog_a = app.deck_a_jogwheel
            
            # Accumulate steering
            self._steering_cumulative += delta * JOG_STEERING_SENSITIVITY
            self._steering_cumulative = max(-1.0, min(1.0, self._steering_cumulative))
            self.state.steering = self._steering_cumulative
        
        # Pitch slider A -> Throttle (inverted: top = full throttle)
        # MIDI 0-127, center at 64
        # Map: 64 (center) = 0 throttle, 0 (top) = full throttle
        pitch_a = app.deck_a_pitch
        if pitch_a <= 64:
            throttle = (64 - pitch_a) / 64.0
        else:
            throttle = 0.0
        self.state.throttle = throttle
        
        # Pitch slider B -> Brake (inverted: top = full brake)
        pitch_b = app.deck_b_pitch
        if pitch_b <= 64:
            brake = (64 - pitch_b) / 64.0
        else:
            brake = 0.0
        self.state.brake = brake
        
        # Volume slider A -> Clutch
        self.state.clutch = app.deck_a_volume / 127.0
        
        # Deck A pads for gear/handbrake
        # Pad 2 (index 1) -> Gear Up
        # Pad 6 (index 5) -> Gear Down  
        # Pad 5 (index 4) -> Handbrake
        gear_up = app.deck_a_pads[1] if len(app.deck_a_pads) > 1 else False
        gear_down = app.deck_a_pads[5] if len(app.deck_a_pads) > 5 else False
        handbrake = app.deck_a_pads[4] if len(app.deck_a_pads) > 4 else False
        
        self.state.gear_up = gear_up
        self.state.gear_down = gear_down
        self.state.handbrake = handbrake
        
        # Write all values to the virtual device
        self._write_state()
        
        # Update last button states
        self._last_gear_up = gear_up
        self._last_gear_down = gear_down
    
    def _write_state(self):
        """Write current state to the virtual device"""
        if not self.device:
            return
        
        # Convert steering from -1.0..1.0 to axis range
        steering_value = int(self.state.steering * self.STEERING_MAX)
        steering_value = max(self.STEERING_MIN, min(self.STEERING_MAX, steering_value))
        
        # Convert pedals from 0.0..1.0 to 0..255
        throttle_value = int(self.state.throttle * self.PEDAL_MAX)
        brake_value = int(self.state.brake * self.PEDAL_MAX)
        clutch_value = int(self.state.clutch * self.PEDAL_MAX)
        
        # Write axes
        self.device.write(e.EV_ABS, e.ABS_WHEEL, steering_value)
        self.device.write(e.EV_ABS, e.ABS_GAS, throttle_value)
        self.device.write(e.EV_ABS, e.ABS_BRAKE, brake_value)
        self.device.write(e.EV_ABS, e.ABS_Z, clutch_value)
        
        # Write buttons
        self.device.write(e.EV_KEY, e.BTN_GEAR_UP, 1 if self.state.gear_up else 0)
        self.device.write(e.EV_KEY, e.BTN_GEAR_DOWN, 1 if self.state.gear_down else 0)
        self.device.write(e.EV_KEY, e.BTN_0, 1 if self.state.handbrake else 0)
        
        # Sync to send all events
        self.device.syn()
    
    def get_status_text(self) -> str:
        """Get a status string for display in TUI"""
        if not self.enabled:
            return "Wheel: OFF"
        
        steering_bar = self._make_steering_bar(self.state.steering)
        return (
            f"Wheel: {steering_bar} | "
            f"Gas:{int(self.state.throttle*100):3}% "
            f"Brk:{int(self.state.brake*100):3}% "
            f"Clt:{int(self.state.clutch*100):3}%"
        )
    
    def _make_steering_bar(self, value: float, width: int = 11) -> str:
        """Create a visual steering bar"""
        # value: -1.0 (left) to 1.0 (right)
        center = width // 2
        pos = int((value + 1.0) / 2.0 * (width - 1))
        pos = max(0, min(width - 1, pos))
        
        bar = ['─'] * width
        bar[center] = '│'
        bar[pos] = '●'
        return '[' + ''.join(bar) + ']'
