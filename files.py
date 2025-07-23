ALLOWED_MIME_TYPES = {
    # Images
    'image/': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
    # Videos
    'video/': ['.mp4', '.webm'],
    # Audio
    'audio/': ['.mp3', '.ogg'],
    # Documents
    'application/pdf': ['.pdf'],
    'text/': ['.txt']
}
MAX_FILE_SIZES = {
    'image': 5 * 1024 * 1024,      # 5MB for images
    'video': 50 * 1024 * 1024,     # 50MB for videos
    'audio': 10 * 1024 * 1024,     # 10MB for audio
    'document': 20 * 1024 * 1024   # 20MB for documents
}