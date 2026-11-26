"""Bounded, read-only extraction of basic MP3 ID3 text tags."""

MAX_TAG_BYTES = 2 * 1024 * 1024
TEXT_FRAMES = {b'TIT2': 'title', b'TPE1': 'artist', b'TALB': 'album'}
ENCODINGS = ('latin-1', 'utf-16', 'utf-16-be', 'utf-8')


def syncsafe(data):
    size = 0
    for byte in data:
        if byte & 128:
            raise ValueError('Invalid ID3 size')
        size = (size << 7) | byte
    return size


def mp3_tags(stream):
    """Read untransformed ID3v2.3/v2.4 text frames, or ID3v1 as a fallback."""
    header = stream.read(10)
    if header[:3] == b'ID3':
        if len(header) != 10:
            raise ValueError('Truncated ID3 header')
        version = header[3]
        if version not in (3, 4) or header[5]:
            raise ValueError('Unsupported ID3 version or flags')
        size = syncsafe(header[6:])
        if size > MAX_TAG_BYTES:
            raise ValueError('ID3 tag exceeds the read limit')
        data = stream.read(size)
        if len(data) != size:
            raise ValueError('Truncated ID3 tag')
        tags = {}
        offset = 0
        while offset < size and data[offset]:
            if size - offset < 10:
                raise ValueError('Truncated ID3 frame header')
            field = TEXT_FRAMES.get(data[offset:offset + 4])
            frame_size = data[offset + 4:offset + 8]
            length = syncsafe(frame_size) if version == 4 else int.from_bytes(frame_size, 'big')
            start = offset + 10
            end = start + length
            if end > size:
                raise ValueError('Truncated ID3 frame')
            if field and length:
                encoding = data[start]
                if encoding >= len(ENCODINGS) or data[offset + 9]:
                    raise ValueError('Unsupported ID3 text frame encoding or flags')
                value = data[start + 1:end].decode(ENCODINGS[encoding]).strip('\0 ')
                if value:
                    tags.setdefault(field, value)
            offset = end
        return tags

    if stream.seek(0, 2) < 128:
        return {}
    stream.seek(-128, 2)
    footer = stream.read(128)
    if footer[:3] != b'TAG':
        return {}
    tags = {}
    for index, field in enumerate(('title', 'artist', 'album')):
        start = 3 + index * 30
        value = footer[start:start + 30].decode('latin-1').strip('\0 ')
        if value:
            tags[field] = value
    return tags
