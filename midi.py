
"""
MIDI input handling for Hercules DJControl Mix Ultra
"""

import asyncio
from typing import Optional, AsyncGenerator, Any
import mido  # type: ignore[import-untyped]


def find_djcontrol_port() -> Optional[str]:
    """Search for a DJControl MIDI input port."""
    for name in mido.get_input_names():  # type: ignore[attr-defined]
        if "DJControl" in name or "Hercules" in name:
            return name
    return None


async def midi_input_generator() -> AsyncGenerator[Any, None]:
    """
    Async generator that yields MIDI messages from the DJControl.
    Automatically searches for and connects to the device.
    """
    port_name = find_djcontrol_port()
    
    if port_name is None:
        raise RuntimeError("DJControl MIDI input not found. Available ports: " + 
                          str(mido.get_input_names()))  # type: ignore[attr-defined]
    
    queue: asyncio.Queue[Any] = asyncio.Queue()
    loop = asyncio.get_event_loop()
    
    def callback(msg: Any) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, msg)
    
    with mido.open_input(port_name, callback=callback):  # type: ignore[attr-defined]
        while True:
            msg = await queue.get()
            yield msg


def get_available_ports() -> list[str]:
    """Return list of available MIDI input ports."""
    return mido.get_input_names()  # type: ignore[attr-defined]