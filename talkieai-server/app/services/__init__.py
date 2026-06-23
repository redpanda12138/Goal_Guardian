"""Application service package.

Service objects are created by request handlers with request-scoped database
sessions. Keep package import side-effect free so starting the API does not
eagerly initialize optional components such as Whisper and Torch.
"""
