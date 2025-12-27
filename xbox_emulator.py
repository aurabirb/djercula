"""
Xbox Controller Emulator Module
Maps Hercules DJControl inputs to virtual Xbox controller.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

JOG_SENSITIVITY = 1 / 720.0  # Sensitivity for jogwheel rotation speed to X-axis

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
    - Pitch sliders -> Left/Right stick Y-axis (up/down, neutral at center)
    - Jog wheels -> Left/Right stick X-axis (left/right based on rotation speed)
    - Volume sliders -> Triggers (LT/RT)
    - Deck A pads 2,5,6,7 -> D-pad (Up, Left, Down, Right)
    - Deck B pads 1,2,5,6 -> Xbox buttons (A, B, X, Y)
    """
    
    def __init__(self):
        self.gamepad: Optional[Any] = None
        self.enabled: bool = False
        self._last_values: Dict[str, Any] = {}
        
        # Last jogwheel values to detect changes
        self._last_jog_a: int = 0
        self._last_jog_b: int = 0
        
        # Base jogwheel position when first touched (for offset calculation)
        self._base_jog_a: int = 0
        self._base_jog_b: int = 0
        
        # Jog push state (True when touching the jog wheel)
        self._jog_push_a: bool = False
        self._jog_push_b: bool = False
        
        # Jog X-axis values (from jogwheel rotation speed)
        self._jog_x_left: float = 0.0
        self._jog_x_right: float = 0.0
        
        # Cumulative jog rotation (resets when jog is touched)
        self._jog_cumulative_left: float = 0.0
        self._jog_cumulative_right: float = 0.0
        
        # Pitch Y-axis values (from pitch sliders)
        self._pitch_y_left: float = 0.0
        self._pitch_y_right: float = 0.0
        
        # Track all pressed buttons to avoid reset() issues
        self._pressed_buttons: set = set()
        
        # Define control mappings - easy to extend!
        self._init_mappings()
    
    def _init_mappings(self):
        """Initialize control mappings. Extend this to add more controls."""
        
        # Continuous control mappings (sliders, encoders)
        self.continuous_mappings = {
            # Pitch sliders -> Stick Y-axis (up/down)
            "deck_a_pitch": {
                "handler": self._handle_pitch,
                "args": {"stick": "left"},
            },
            "deck_b_pitch": {
                "handler": self._handle_pitch,
                "args": {"stick": "right"},
            },
            # Jog wheels -> Stick X-axis (left/right based on rotation speed)
            "deck_a_jogwheel": {
                "handler": self._handle_jogwheel,
                "args": {"stick": "left"},
            },
            "deck_b_jogwheel": {
                "handler": self._handle_jogwheel,
                "args": {"stick": "right"},
            },
            # Volume sliders -> Triggers
            "deck_a_volume": {
                "handler": self._handle_trigger,
                "args": {"trigger": "left"},
            },
            "deck_b_volume": {
                "handler": self._handle_trigger,
                "args": {"trigger": "right"},
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
        self._last_jog_a = 0
        self._last_jog_b = 0
        self._jog_push_a = False
        self._jog_push_b = False
        self._jog_x_left = 0.0
        self._jog_x_right = 0.0
        self._jog_cumulative_left = 0.0
        self._jog_cumulative_right = 0.0
        self._pitch_y_left = 0.0
        self._pitch_y_right = 0.0
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
        """Handle trigger input from volume sliders (0-127 -> 0-255)"""
        # Convert MIDI value (0-127) to trigger value (0-255)
        # Volume at 0 = no trigger, volume at 127 = full trigger
        trigger_value = int(value * 2)
        trigger_value = max(0, min(255, trigger_value))
        
        if trigger == "left":
            self.gamepad.left_trigger(value=trigger_value)
        elif trigger == "right":
            self.gamepad.right_trigger(value=trigger_value)
    
    def _handle_pitch(self, value: int, stick: str):
        """Handle pitch slider input - controls stick Y-axis with neutral at center"""
        # Convert MIDI value (0-127) to Y value (-1.0 to 1.0)
        # 64 (center) = 0.0, 0 (bottom) = -1.0, 127 (top) = 1.0
        y_value = (value - 64) / 64.0
        y_value = max(-1.0, min(1.0, y_value))
        
        if stick == "left":
            self._pitch_y_left = y_value
            # Combine with jog X value
            x_value = getattr(self, '_jog_x_left', 0.0)
            self.gamepad.left_joystick_float(x_value_float=x_value, y_value_float=y_value)
        elif stick == "right":
            self._pitch_y_right = y_value
            # Combine with jog X value
            x_value = getattr(self, '_jog_x_right', 0.0)
            self.gamepad.right_joystick_float(x_value_float=x_value, y_value_float=y_value)
    
    def _handle_jog_push(self, pressed: bool, stick: str):
        """Handle jog wheel touch state - X-axis returns to neutral when released"""
        if stick == "left":
            was_pushed = self._jog_push_a
            self._jog_push_a = pressed
            if pressed and not was_pushed:
                # Just touched - reset cumulative rotation
                self._base_jog_a = self._last_jog_a
                self._jog_x_left = 0.0
                self._jog_cumulative_left = 0.0
            elif not pressed:
                # Released - return X to neutral, keep Y from pitch
                self._jog_x_left = 0.0
                self._jog_cumulative_left = 0.0
                y_value = getattr(self, '_pitch_y_left', 0.0)
                self.gamepad.left_joystick_float(x_value_float=0.0, y_value_float=y_value)
        elif stick == "right":
            was_pushed = self._jog_push_b
            self._jog_push_b = pressed
            if pressed and not was_pushed:
                # Just touched - reset cumulative rotation
                self._base_jog_b = self._last_jog_b
                self._jog_x_right = 0.0
                self._jog_cumulative_right = 0.0
            elif not pressed:
                # Released - return X to neutral, keep Y from pitch
                self._jog_x_right = 0.0
                self._jog_cumulative_right = 0.0
                y_value = getattr(self, '_pitch_y_right', 0.0)
                self.gamepad.right_joystick_float(x_value_float=0.0, y_value_float=y_value)
    
    def _handle_jogwheel(self, value: int, stick: str):
        """
        Handle jogwheel input - maps cumulative rotation to stick X-axis (left/right).
        - Cumulative rotation determines X deflection
        - Clockwise = right, counter-clockwise = left
        - Only active when jog is touched (jog_push)
        """
        if stick == "left":
            # Calculate delta from last value
            delta = value - self._last_jog_a
            self._last_jog_a = value
            
            # # Handle wraparound (0-255)
            # if delta > 128:
            #     delta -= 256
            # elif delta < -128:
            #     delta += 256
            
            # Skip if jog not touched
            if not self._jog_push_a:
                return
            
            # Accumulate rotation and convert to X value (-1.0 to 1.0)
            # Full rotation (256 ticks) = full stick deflection
            self._jog_cumulative_left += delta * JOG_SENSITIVITY
            x_value = max(-1.0, min(1.0, self._jog_cumulative_left))
            
            self._jog_x_left = x_value
            y_value = getattr(self, '_pitch_y_left', 0.0)
            self.gamepad.left_joystick_float(x_value_float=x_value, y_value_float=y_value)
        
        elif stick == "right":
            delta = value - self._last_jog_b
            self._last_jog_b = value
            
            if delta > 128:
                delta -= 256
            elif delta < -128:
                delta += 256
            
            if not self._jog_push_b:
                return
            
            # Accumulate rotation and convert to X value (-1.0 to 1.0)
            self._jog_cumulative_right += delta * JOG_SENSITIVITY
            x_value = max(-1.0, min(1.0, self._jog_cumulative_right))
            
            self._jog_x_right = x_value
            y_value = getattr(self, '_pitch_y_right', 0.0)
            self.gamepad.right_joystick_float(x_value_float=x_value, y_value_float=y_value)
    
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
