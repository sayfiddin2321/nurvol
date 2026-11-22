def consume_response(response):
    """Finish file responses through Django's test-client cleanup wrapper."""
    if response.streaming:
        for _ in response.streaming_content:
            pass
