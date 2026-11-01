"""Run with python test_audio.py. Exercises stream lifecycle and WAV decoding."""
import asyncio
import importlib.util
import pathlib
import struct
import subprocess

path = pathlib.Path(__file__).parents[1] / 'custom_components/interphone_live/audio.py'
spec = importlib.util.spec_from_file_location('interphone_audio', path)
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)

async def test():
    s = audio.AudioSession(object(), 'media_player.test', 'token')
    chunks = []
    async def read():
        async for chunk in s.chunks():
            chunks.append(chunk)
    reader = asyncio.create_task(read())
    await asyncio.sleep(0)
    pcm = struct.pack('<1600h', *([1000] * 1600))
    await s.append(pcm)
    await asyncio.sleep(0)
    await s.append(pcm)
    await s.finish()
    await asyncio.wait_for(reader, 1)
    assert b''.join(chunks) == pcm * 2
    assert len(audio.wav_header()) == 44
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', 'pipe:0',
        '-f', 's16le', 'pipe:1'], input=audio.wav_header() + pcm * 2,
        capture_output=True, check=True).stdout
    assert decoded == pcm * 2
    try:
        await s.append(pcm)
        raise AssertionError('Ended session accepted audio')
    except ValueError:
        pass
    s2 = audio.AudioSession(None, '', '')
    for _ in range(100):
        await s2.append(bytes(2560))
    assert len(s2.frames) == 64
    assert sum(len(chunk) for _, chunk in s2.frames) == 163840
    try:
        await s2.append(bytes(4098))
        raise AssertionError('Oversize chunk accepted')
    except ValueError:
        pass
    await s2.finish()
    replay = [chunk async for chunk in s2.chunks()]
    assert len(replay) == 64
    print('PASS: WAV decoder, concurrent live delivery, EOF, bounded replay, size and lifecycle guards')

asyncio.run(test())
