"""
Xbox Controller Emulator Module
Maps Hercules DJControl inputs to virtual Xbox controller.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import math

try:
    import vgamepad as vg
    VGAMEPAD_AVAILABLE = True
except ImportError:
    VGAMEPAD_AVAILABLE = False


@dataclass
class XboxMapping:
    """Defines a mapping from DJ control to Xbox control"""
    source_attr: str  # Attribute name in DJControlApp
    handler: str  # Handler method name
    xbox_control: Any  # Xbox control identifier
    
    # Optional transform parameters
    invert: bool = False
    deadzone: float = 0.05
    sensitivity: float = 1.0


class XboxEmulator:
    """
    Emulates Xbox controller using DJ controller inputs.
    
    Mappings:
    - Jog wheels -> Left/Right stick rotation (circular motion)
    - Pitch sliders -> Triggers (LT/RT)
    - Deck A pads 2,5,6,7 -> D-pad (Up, Left, Down, Right)
    - Deck B pads 1,2,5,6 -> Xbox buttons (A, B, X, Y)
    """
    
    def __init__(self):
        self.gamepad: Optional[Any] = None
        self.enabled: bool = False
        self._last_values: Dict[str, Any] = {}
        
        # Jog wheel cumulative angle tracking (for stick rotation)
        self.jog_a_angle: float = 0.0
        self.jog_b_angle: float = 0.0
        
        # Last jogwheel values to detect changes
        self._last_jog_a: int = 0
        self._last_jog_b: int = 0
        
        # Jog push state (True when touching the jog wheel)
        self._jog_push_a: bool = False
        self._jog_push_b: bool = False
        
        # Stick intensity (ramps up as jog is turned, 0.0 to 1.0)
        self._stick_intensity_a: float = 0.0
        self._stick_intensity_b: float = 0.0
        
        # Track all pressed buttons to avoid reset() issues
        self._pressed_buttons: set = set()
        
        # Define control mappings - easy to extend!
        self._init_mappings()
    
    def _init_mappings(self):
        """Initialize control mappings. Extend this to add more controls."""
        
        # Continuous control mappings (sliders, encoders)
        self.continuous_mappings = {
            # Pitch sliders -> Triggers
            "deck_a_pitch": {
                "handler": self._handle_trigger,
                "args": {"trigger": "left"},
            },
            "deck_b_pitch": {
                "handler": self._handle_trigger,
                "args": {"trigger": "right"},
            },
            # Jog wheels -> Stick rotation
            "deck_a_jogwheel": {
                "handler": self._handle_jogwheel,
                "args": {"stick": "left"},
            },
            "deck_b_jogwheel": {
                "handler": self._handle_jogwheel,
                "args": {"stick": "right"},
            },
            # Jog push -> controls stick active state
            "jog_push_a": {
                "handler": self._handle_jog_push,
                "args": {"stick": "left"},
            },
            "jog_push_b": {
                "handler": self._handle_jog_push,
                "args": {"stick": "right"},
            },
        }
        
        # Button mappings (pads, buttons)
        # Deck A pads -> D-pad: 2=Up, 5=Left, 6=Down, 7=Right
        # Deck B pads -> Xbox: 1=A, 2=B, 5=X, 6=Y
        self.button_mappings = {
            # D-pad (Deck A pads)
            "deck_a_pads_2": {
                "handler": self._handle_dpad,
                "args": {"direction": "up"},
            },
            "deck_a_pads_5": {
                "handler": self._handle_dpad,
                "args": {"direction": "left"},
            },
            "deck_a_pads_6": {
                "handler": self._handle_dpad,
                "args": {"direction": "down"},
            },
            "deck_a_pads_7": {
                "handler": self._handle_dpad,
                "args": {"direction": "right"},
            },
            
            # Xbox buttons (Deck B pads)
            "deck_b_pads_1": {
                "handler": self._handle_button,
                "args": {"button": "a"},
            },
            "deck_b_pads_2": {
                "handler": self._handle_button,
                "args": {"button": "b"},
            },
            "deck_b_pads_5": {
                "handler": self._handle_button,
                "args": {"button": "x"},
            },
            "deck_b_pads_6": {
                "handler": self._handle_button,
                "args": {"button": "y"},
            },
            
            # Browse encoder push -> Xbox Guide button
            "browse_push": {
                "handler": self._handle_button,
                "args": {"button": "guide"},
            },
            
            # Load buttons -> Back/Start
            "load_a": {
                "handler": self._handle_button,
                "args": {"button": "back"},
            },
            "load_b": {
                "handler": self._handle_button,
                "args": {"button": "start"},
            },
        }
        
        # D-pad state tracking (need to combine for proper D-pad handling)
        self.dpad_state = {
            "up": False,
            "down": False,
            "left": False,
            "right": False,
        }
    
    @property
    def available(self) -> bool:
        """Check if vgamepad is available"""
        return VGAMEPAD_AVAILABLE
    
    def start(self) -> bool:
        """Start the Xbox controller emulation"""
        if not VGAMEPAD_AVAILABLE:
            return False
        
        try:
            self.gamepad = vg.VX360Gamepad()
            self.enabled = True
            self._reset_state()
            return True
        except Exception as e:
            print(f"Failed to create virtual gamepad: {e}")
            return False
    
    def stop(self):
        """Stop the Xbox controller emulation"""
        if self.gamepad:
            self._reset_state()
            self.gamepad = None
        self.enabled = False
    
    def _reset_state(self):
        """Reset all controls to neutral"""
        if not self.gamepad:
            return
        
        self.gamepad.reset()
        self.gamepad.update()
        self.jog_a_angle = 0.0
        self.jog_b_angle = 0.0
        self._last_jog_a = 0
        self._last_jog_b = 0
        self._jog_push_a = False
        self._jog_push_b = False
        self._stick_intensity_a = 0.0
        self._stick_intensity_b = 0.0
        self._pressed_buttons.clear()
        self.dpad_state = {k: False for k in self.dpad_state}
        self._last_values.clear()
    
    def update_from_app(self, app):
        """
        Update Xbox controller state from DJControlApp state.
        Call this after processing MIDI messages.
        """
        if not self.enabled or not self.gamepad:
            return
        
        # Process continuous controls
        for attr_name, mapping in self.continuous_mappings.items():
            value = self._get_app_value(app, attr_name)
            if value is not None:
                mapping["handler"](value, **mapping["args"])
        
        # Process button controls
        for attr_name, mapping in self.button_mappings.items():
            value = self._get_app_value(app, attr_name)
            if value is not None:
                mapping["handler"](value, **mapping["args"])
        
        # Apply all updates
        self.gamepad.update()
    
    def _get_app_value(self, app, attr_name: str):
        """Get a value from the app, handling pad array access"""
        if "_pads_" in attr_name:
            # Handle pad access: deck_a_pads_2 -> app.deck_a_pads[1]
            parts = attr_name.rsplit("_", 1)
            pad_attr = parts[0]  # deck_a_pads
            pad_idx = int(parts[1]) - 1  # 0-indexed
            pads = getattr(app, pad_attr, None)
            if pads and 0 <= pad_idx < len(pads):
                return pads[pad_idx]
            return None
        else:
            return getattr(app, attr_name, None)
    
    def _handle_trigger(self, value: int, trigger: str):
        """Handle trigger input (0-127 -> 0-255)"""
        # Convert MIDI value (0-127) to trigger value (0-255)
        # Invert so that 127 (top position) = 0, 0 (bottom) = 255
        trigger_value = int((127 - value) * 2)
        trigger_value = max(0, min(255, trigger_value))
        
        if trigger == "left":
            self.gamepad.left_trigger(value=trigger_value)
        elif trigger == "right":
            self.gamepad.right_trigger(value=trigger_value)
    
    def _handle_jog_push(self, pressed: bool, stick: str):
        """Handle jog wheel touch state - sticks return to neutral when released"""
        if stick == "left":
            was_pushed = self._jog_push_a
            self._jog_push_a = pressed
            if pressed and not was_pushed:
                # Just touched - reset intensity to start from 0
                self._stick_intensity_a = 0.0
            elif not pressed:
                # Released - return stick to neutral
                self._stick_intensity_a = 0.0
                self.gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
        elif stick == "right":
            was_pushed = self._jog_push_b
            self._jog_push_b = pressed
            if pressed and not was_pushed:
                self._stick_intensity_b = 0.0
            elif not pressed:
                self._stick_intensity_b = 0.0
                self.gamepad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
    
    def _handle_jogwheel(self, value: int, stick: str):
        """
        Handle jogwheel input - maps rotation to stick circular motion.
        - 5x reduced sensitivity
        - Only active when jog is touched (jog_push)
        - Intensity ramps up as jog is turned
        """
        if stick == "left":
            # Calculate delta from last value
            delta = value - self._last_jog_a
            self._last_jog_a = value
            
            # Handle wraparound (0-255)
            if delta > 128:
                delta -= 256
            elif delta < -128:
                delta += 256
            
            # Skip if no change or jog not touched
            if delta == 0 or not self._jog_push_a:
                return
            
            # Convert delta to angle change (5x reduced sensitivity: /160.0 instead of /32.0)
            angle_delta = (delta / 160.0) * math.pi
            self.jog_a_angle += angle_delta
            self.jog_a_angle %= (math.pi * 2)
            
            # Ramp up intensity (increases with each movement, max 1.0)
            self._stick_intensity_a = min(1.0, self._stick_intensity_a + abs(delta) / 100.0)
            
            # Convert angle to stick X/Y, scaled by intensity
            intensity = self._stick_intensity_a
            x = math.cos(self.jog_a_angle) * intensity
            y = math.sin(self.jog_a_angle) * intensity
            self.gamepad.left_joystick_float(x_value_float=x, y_value_float=y)
        
        elif stick == "right":
            delta = value - self._last_jog_b
            self._last_jog_b = value
            
            if delta > 128:
                delta -= 256
            elif delta < -128:
                delta += 256
            
            if delta == 0 or not self._jog_push_b:
                return
            
            angle_delta = (delta / 160.0) * math.pi
            self.jog_b_angle += angle_delta
            self.jog_b_angle %= (math.pi * 2)
            
            self._stick_intensity_b = min(1.0, self._stick_intensity_b + abs(delta) / 100.0)
            
            intensity = self._stick_intensity_b
            x = math.cos(self.jog_b_angle) * intensity
            y = math.sin(self.jog_b_angle) * intensity
            self.gamepad.right_joystick_float(x_value_float=x, y_value_float=y)
    
    def _handle_dpad(self, pressed: bool, direction: str):
        """Handle D-pad button press"""
        self.dpad_state[direction] = pressed
        self._update_dpad()
    
    def _update_dpad(self):
        """Update D-pad state based on combined button states"""
        # Map direction combinations to vgamepad D-pad values
        up = self.dpad_state["up"]
        down = self.dpad_state["down"]
        left = self.dpad_state["left"]
        right = self.dpad_state["right"]
        
        # D-pad button constants
        dpad_up = vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP
        dpad_down = vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN
        dpad_left = vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT
        dpad_right = vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT
        
        # Release all D-pad buttons first
        for btn in [dpad_up, dpad_down, dpad_left, dpad_right]:
            self.gamepad.release_button(btn)
            self._pressed_buttons.discard(btn)
        
        # Press the appropriate D-pad buttons
        if up:
            self.gamepad.press_button(dpad_up)
            self._pressed_buttons.add(dpad_up)
        if down:
            self.gamepad.press_button(dpad_down)
            self._pressed_buttons.add(dpad_down)
        if left:
            self.gamepad.press_button(dpad_left)
            self._pressed_buttons.add(dpad_left)
        if right:
            self.gamepad.press_button(dpad_right)
            self._pressed_buttons.add(dpad_right)
    
    def _handle_button(self, pressed: bool, button: str):
        """Handle Xbox face button press"""
        button_map = {
            "a": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
            "b": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
            "x": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
            "y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
            "lb": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
            "rb": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
            "start": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
            "back": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
            "guide": vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
            "left_thumb": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
            "right_thumb": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
        }
        
        if button not in button_map:
            return
        
        xbox_button = button_map[button]
        if pressed:
            self.gamepad.press_button(xbox_button)
            self._pressed_buttons.add(xbox_button)
        else:
            self.gamepad.release_button(xbox_button)
            self._pressed_buttons.discard(xbox_button)


# Convenience function to add new mappings
def add_continuous_mapping(emulator: XboxEmulator, source_attr: str, 
                           handler_name: str, **handler_args):
    """Add a new continuous control mapping to the emulator"""
    handler = getattr(emulator, handler_name, None)
    if handler:
        emulator.continuous_mappings[source_attr] = {
            "handler": handler,
            "args": handler_args,
        }


def add_button_mapping(emulator: XboxEmulator, source_attr: str,
                       handler_name: str, **handler_args):
    """Add a new button mapping to the emulator"""
    handler = getattr(emulator, handler_name, None)
    if handler:
        emulator.button_mappings[source_attr] = {
            "handler": handler,
            "args": handler_args,
        }
