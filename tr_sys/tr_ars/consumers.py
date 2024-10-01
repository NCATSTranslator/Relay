from channels.generic.websocket import WebsocketConsumer
import json
import logging

# Initialize logger
logger = logging.getLogger(__name__)

class ARSConsumer(WebsocketConsumer):
    def connect(self):
        self.accept()
        logger.info("WebSocket connection accepted.")
    def disconnect(self, close_code):
        logger.info(f"WebSocket connection closed with code {close_code}.")
        pass

    def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json['message']
            if not message:
                logger.warning("Received empty message.")
            # Echo the message back to the client
            self.send(text_data=json.dumps({
                'message': message
            }))
            logger.info(f"Message received and sent back: {message}")

        except json.JSONDecodeError:
            # Handle invalid JSON data
            logger.error("Failed to decode JSON. Invalid message format.")
            self.send(text_data=json.dumps({
                'error': 'Invalid JSON format'
            }))
