"""Bounded, ephemeral PCM stream. No audio is saved to disk."""
import asyncio
import struct
import time
from collections import deque

RATE = 16000
MAX_SECONDS = 60

def wav_header():
    # Indefinite-length PCM WAV; FFmpeg accepts the unknown-length sentinel.
    return struct.pack('<4sI4s4sIHHIIHH4sI', b'RIFF', 0xffffffff, b'WAVE',
                       b'fmt ', 16, 1, 1, RATE, RATE * 2, 2, 16,
                       b'data', 0xffffffff)

class AudioSession:
    def __init__(self, owner, target, token):
        self.owner, self.target, self.token = owner, target, token
        self.started = self.last_audio = time.monotonic()
        self.frames = deque(maxlen=64)
        self.next_index = self.bytes_received = self.readers = 0
        self.max_readers = 0
        self.ended = False
        self.error = None
        self.playback_requested = False
        self.condition = asyncio.Condition()
        self.sequence = 0

    async def append(self, data):
        if self.ended:
            raise ValueError('Transmission arrêtée')
        if not data or len(data) > 4096 or len(data) % 2:
            raise ValueError('Bloc PCM invalide')
        self.frames.append((self.next_index, data))
        self.next_index += 1
        self.bytes_received += len(data)
        self.last_audio = time.monotonic()
        async with self.condition:
            self.condition.notify_all()

    async def finish(self):
        self.ended = True
        async with self.condition:
            self.condition.notify_all()

    async def chunks(self):
        cursor = self.frames[0][0] if self.frames else self.next_index
        while True:
            found = [(i, chunk) for i, chunk in self.frames if i >= cursor]
            for i, chunk in found:
                cursor = i + 1
                yield chunk
            if self.ended:
                return
            async with self.condition:
                # Recheck after taking the condition: no lost wakeup.
                if self.next_index > cursor:
                    continue
                try:
                    await asyncio.wait_for(self.condition.wait(), 2)
                except TimeoutError:
                    if time.monotonic() - self.last_audio > 3:
                        return
