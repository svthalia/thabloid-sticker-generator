class InvalidApiKeyException(Exception):
    def __init__(self, message):
        self.message = f"Failed to check entries: {message}"


class InvalidAddressException(Exception):
    def __init__(self, message, query=False):
        self.message = message
        self.query = query
