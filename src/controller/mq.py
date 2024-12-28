import pika
import time
import logging

# 创建一个logger对象
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # 设置日志级别
 
# 创建一个处理器，用于将日志输出到控制台
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)  # 设置处理器的日志级别
  
# 创建一个日志格式器，并将其添加到处理器中
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
   
# 将处理器添加到logger对象中
logger.addHandler(console_handler)

class RabbitMQConsumer:
    def __init__(self, host='localhost', port=5672, username='admin', password='V2SG@xdr', queue_name='', exchange_name='', routing_key='', consume_callback=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.queue_name = queue_name
        self.exchange_name = exchange_name
        self.routing_key = routing_key
        self.consume_callback = consume_callback
        self.retry_interval = 5
        self.connection = None
        self.channel = None
        self.stopping = False

    def connect(self):
        """Establish a connection to RabbitMQ, with retries."""
        while not self.stopping:
            try:
                logger.info("Attempting to connect to RabbitMQ...")
                self.connection = pika.BlockingConnection(pika.ConnectionParameters(
                    host=self.host, port=self.port,
                    credentials=pika.PlainCredentials(self.username, self.password)
                ))
                self.channel = self.connection.channel()
                self.channel.exchange_declare(exchange=self.exchange_name, exchange_type='direct', durable=True)
                self.channel.queue_declare(queue=self.queue_name, durable=True)
                self.channel.queue_bind(exchange=self.exchange_name, queue=self.queue_name, routing_key=self.routing_key)

                logger.info("Connected to RabbitMQ. Starting to consume messages...")
                self.consume()
            except (pika.exceptions.AMQPConnectionError, pika.exceptions.AMQPChannelError) as error:
                logger.error(f"Failed to connect to RabbitMQ: {error}. Retrying in {self.retry_interval} seconds...")
                time.sleep(self.retry_interval)
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}")
                self.stopping = True  # Stop trying to reconnect if an unexpected error occurs

    def set_consume_callback(self, cb):
        self.consume_callback = cb

    def consume(self):
        """Consume messages from the queue."""
        def callback(ch, method, properties, body):
            logger.info("Received message: %r, %r, %r, %r", ch, method, properties, body)

        self.channel.basic_consume(queue=self.queue_name, on_message_callback=self.consume_callback, auto_ack=True)

        try:
            self.channel.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            logger.error("Lost connection to RabbitMQ. Attempting to reconnect...")
            self.connection.close()
            self.connect()

    def stop(self):
        """Stop the consumer."""
        self.stopping = True
        if self.connection:
            self.connection.close()

if __name__ == "__main__":
    def test_cb(ch, method, properties, body):
        logger.info("Received message: %r, %r, %r, %r", ch, method, properties, body)
    consumer = RabbitMQConsumer(queue_name='va_task_12345', exchange_name='va_task', routing_key='va_task_12345', consume_callback=test_cb)
    consumer.connect()
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        consumer.stop()
